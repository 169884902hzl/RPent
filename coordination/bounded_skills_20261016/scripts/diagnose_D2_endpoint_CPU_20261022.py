"""Replay saved controls and inspect native predicates across a zero-step forward."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys


def pinned(ref):
    raw = Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('artifact changed: '+ref['path'])
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--sampling', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro',
        MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl', OPENBLAS_NUM_THREADS='1')
    import robots.libero.env_server  # configure GL before native imports
    import rlinf.envs.libero.libero_env  # route the owned D2 development package
    import mujoco
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.v5_branch_state import restore_actuators, native_data_state, restore_native_data

    replay, sampling = json.loads(args.summary.read_bytes()), json.loads(args.sampling.read_bytes())
    initial = pickle.loads(pinned(replay['parent_initial']))['physics']
    trial = replay['full_replay'][0]
    endpoint = pickle.loads(pinned(trial['endpoint']))['physics']
    choices = [json.loads(line) for line in pinned(trial['choices']).splitlines()]
    actions = [row['action'] for choice in choices for detail in choice['execution_details']
        for row in detail.get('execution', {}).get('trace', [])]
    case = sampling['case']
    pinned(case['bddl'])
    env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
        has_renderer=False, has_offscreen_renderer=False, camera_names=[],
        ignore_done=True, horizon=10015)

    def restore(snapshot):
        env.set_init_state(snapshot['sim_state'])
        actuators = copy.deepcopy(snapshot['actuator_state'])
        actuators.pop('observation_state', None)
        restore_actuators(env, actuators)

    def status():
        sim = env.sim
        names = lambda g: mujoco.mj_id2name(sim.model._model, mujoco.mjtObj.mjOBJ_GEOM, int(g))
        return {'done': bool(env.check_success()), 'time': float(sim.data.time),
            'qpos_sha256': hashlib.sha256(np.asarray(sim.data.qpos).tobytes()).hexdigest(),
            'contacts': [{'geoms': [names(c.geom1), names(c.geom2)], 'distance_m': float(c.dist)}
                for c in sim.data.contact[:sim.data.ncon]
                if any('bowl' in (names(g) or '') or 'plate' in (names(g) or '')
                    for g in (c.geom1, c.geom2))]}
    try:
        env.reset()
        restore(initial)
        initial_residual = float(np.max(np.abs(env.sim.get_state().flatten()-initial['sim_state'])))
        for action in actions:
            env.step(np.asarray(action))
        before = status()
        native = native_data_state(env)
        endpoint_residual = float(np.max(np.abs(env.sim.get_state().flatten()-endpoint['sim_state'])))
        env.sim.forward()
        after_forward = status()
        restore_native_data(env, native)
        after_native_copy = status()
        native_identical = native_data_state(env)['sha256'] == native['sha256']
        restore(endpoint)
        after_restore = status()
        result = {'scope': 'private D2 CPU saved-control replay; no policy, renderer, training or rescore',
            'source': str(args.source), 'summary': str(args.summary),
            'summary_sha256': hashlib.sha256(args.summary.read_bytes()).hexdigest(),
            'steps': len(actions), 'initial_max_residual': initial_residual,
            'endpoint_max_residual': endpoint_residual, 'before_forward': before,
            'after_zero_step_forward': after_forward, 'after_endpoint_restore': after_restore,
            'after_native_buffer_restore': after_native_copy,
            'native_buffers_byte_identical': native_identical,
            'observation_buffers': 'omitted only in this renderer-free private diagnosis',
            'original_private_truth': json.loads(pinned(trial['evidence']))}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({key: result[key] for key in ('steps', 'initial_max_residual', 'endpoint_max_residual')} |
            {'done_before': before['done'], 'done_after_forward': after_forward['done'],
             'done_after_restore': after_restore['done'],
             'done_after_native_buffer_restore': after_native_copy['done'],
             'native_buffers_byte_identical': native_identical, 'output': str(args.output)}))
    finally:
        env.close()


if __name__ == '__main__':
    main()
