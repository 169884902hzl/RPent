"""Owned original oracle with complete chunks and optional registered reset bytes."""

import copy
import hashlib
import json
import os
import types
from pathlib import Path

import numpy as np


def main():
    from robots.libero import v5_oracle_server as oracle
    from rpent.utils.serialization import to_numpy_tree
    from scripts.probe_v5_skill501_original import complete_probe_chunk
    from robots.libero import v5_branch_state

    original_attach = v5_branch_state.attach_branch_state

    def reset_layout_controllers(wrapper):
        env = wrapper.env
        for robot in env.robots:
            for arm in robot.arms:
                controller = robot.part_controllers[arm]
                controller.update(force=True)
                controller.reset_goal()
        wrapper._update_observables(force=True)
        return env._get_observations()

    def attach_layout_controller_reset(wrapper):
        wrapper = original_attach(wrapper)
        wrapper.v5_layout_controller_sensor_reset = types.MethodType(reset_layout_controllers, wrapper)
        return wrapper

    v5_branch_state.attach_branch_state = attach_layout_controller_reset

    class TransferFacade(oracle.OriginalOracleFacade):
        def __init__(self, *args, **kwargs):
            self._skill_chunk_accounting = {
                'version': 'owned-original-moka-complete-chunks/1',
                'chunks_requested': 0, 'requested_controls': 0,
                'executed_controls': 0, 'raw_native_success_controls': 0,
                'external_truncation': False, 'native_success_stops_chunk': False,
                'private_joint_or_predicate_used_for_control': False,
            }
            self._registered_reset_evidence = None
            super().__init__(*args, **kwargs)

        def _register_rpc(self):
            super()._register_rpc()
            self._rpc['diagnostic.moka_chunks'] = lambda: copy.deepcopy(self._skill_chunk_accounting)
            self._rpc['diagnostic.moka_registered_reset'] = lambda: copy.deepcopy(self._registered_reset_evidence)
            self._readonly_methods.update(('diagnostic.moka_chunks', 'diagnostic.moka_registered_reset'))

        def reset(self):
            observation, info = super().reset()
            ref_text = os.environ.get('MOKA_TRANSFER_REGISTERED_STATE_REFERENCE')
            if not ref_text:
                return observation, info
            ref = json.loads(ref_text)
            path = Path(ref['path']).resolve(strict=True)
            if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
                raise ValueError('Registered layout rawstate file changed')
            registered = json.loads(path.read_text())
            ep = registered['episode']
            if any(ep[key] != self._meta[key] for key in ('suite', 'task', 'seed')):
                raise ValueError('Registered layout belongs to another original scene')
            if registered['bddl']['sha256'] != self._bddl_sha:
                raise ValueError('Original task goal asset changed')
            state = np.asarray(registered['rawstate'], dtype='<f8', order='C')
            digest = hashlib.sha256(state.tobytes()).hexdigest()
            if digest != registered['state_sha256']:
                raise ValueError('Registered layout rawstate hash changed')
            worker = self._env.env.workers[0]
            raw = worker.set_init_state(state)
            # Rebuild controller goals and raw camera/proprioception sensors from
            # the registered state before the client creates its perception scene.
            raw = worker.env_call('v5_layout_controller_sensor_reset', target='self')
            self._env.current_raw_obs = [raw]
            observed = np.asarray(worker.get_sim_state(), dtype='<f8', order='C')
            if not np.allclose(observed, state, atol=1e-8, rtol=0):
                raise RuntimeError('Registered layout was not restored exactly')
            self._registered_reset_evidence = {
                'registered_state_file': ref, 'state_sha256': digest,
                'layout_seed': registered['layout_seed'], 'episode': ep,
                'max_absolute_restore_error': float(np.max(np.abs(observed-state))),
                'task_goal_changed': False, 'policy_has_rawstate_access': False,
                'proposed_state_sha256': registered['preparation_provenance']['proposed_state_sha256'],
                'settled_state_sha256': registered['preparation_provenance']['settled_state_sha256'],
                'restored_state_sha256': hashlib.sha256(observed.tobytes()).hexdigest(),
                'preparation_geometry': registered['preparation_provenance']['settled_geometry'],
                'restored_private_geometry': worker.env_call('v5_reference_geometry', target='self'),
                'geometry_fingerprint': registered['preparation_provenance']['geometry_fingerprint'],
                'restore_stage': 'environment_reset_before_client_scene_and_first_perception',
                'raw_sensor_observables_forced': True, 'controller_goals_reset': True,
            }
            return self._strip_obs(to_numpy_tree(self._env._wrap_obs([raw]))), info

        def chunk_step(self, actions, *, return_all_frames=False):
            return complete_probe_chunk(self, actions, return_all_frames=return_all_frames)

    oracle.OriginalOracleFacade = TransferFacade
    oracle.main()


if __name__ == '__main__':
    main()
