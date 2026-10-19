"""Check whether an identical saved state yields history-dependent preparation."""
import argparse
import copy
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--branch-state-source', type=Path)
    parser.add_argument('--complete-reference', action='store_true')
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro')
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import robots.libero.env_server
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero import v5_branch_state
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    if args.branch_state_source:
        module_spec = importlib.util.spec_from_file_location('branch_state_under_test', args.branch_state_source)
        v5_branch_state = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(v5_branch_state)

    row = next(r for r in json.loads(args.registry.read_bytes())['rows'] if r['seed'] == 13402000)
    saved = pickle.loads(Path(row['branchpoint']).read_bytes())
    physics = saved['physics']
    old = json.loads(Path(row['raw_summary']).read_bytes())
    execution = next(d['execution'] for line in Path(old['choices']['path']).open()
        for d in json.loads(line)['execution_details'] if 'skill_stop_reason' in d.get('execution', {}))
    actions = [np.asarray(t['action']) for t in execution['preparation']['trace']]
    assignment = json.loads(Path(row['raw_summary']).parents[3].joinpath('assignment.json').read_bytes())
    case = assignment['case']
    rows = []
    for warm_final in (False, True):
        env = v5_branch_state.attach_branch_state(ControlEnv(bddl_file_name=case['bddl']['path'],
            has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False, camera_names=[],
            ignore_done=True, hard_reset=False, horizon=10015))
        try:
            env.seed(case['episode']['seed'])
            env.reset()
            reference = physics
            def restore():
                env.set_init_state(reference['sim_state'])
                obs = v5_branch_state.restore_actuators(env, reference['actuator_state'])
                if warm_final:
                    env.env.sim.data.qacc_warmstart[:] = reference['actuator_state']['data']['qacc_warmstart']
                return obs
            if args.complete_reference:
                restore()
                reference = {**physics, 'sim_state': env.get_sim_state(),
                    'actuator_state': v5_branch_state.actuator_state(env)}
            for preceding_controls in (0, 1, 10, 100):
                restore()
                for _ in range(preceding_controls):
                    env.step(np.r_[np.zeros(6), -1.])
                obs = restore()
                actual = copy.deepcopy(reference)
                actual.update(sim_state=env.get_sim_state(), actuator_state=v5_branch_state.actuator_state(env))
                clock = {name: getattr(env.env, name, None) for name in ('timestep', 'cur_time')}
                initial_qpos = np.array(env.env.sim.data.qpos, copy=True)
                for action in actions:
                    obs = env.step(action)[0]
                rows.append({'warmstart_restored_last': warm_final, 'preceding_controls': preceding_controls,
                    'same_captured_physics': snapshot_digest(actual) == snapshot_digest(reference),
                    'worker_clock_after_restore': clock, 'initial_qpos': initial_qpos.tolist(),
                    'after_preparation_qpos': env.env.sim.data.qpos.tolist(),
                    'after_preparation_observed_gripper': np.asarray(obs['robot0_gripper_qpos']).tolist(),
                    'old_observed_gripper': execution['trace'][0]['before']['finger_positions_m']})
        finally:
            env.close()
    for warm in (False, True):
        group = [r for r in rows if r['warmstart_restored_last'] == warm]
        for r in group:
            r['max_qpos_delta_from_no_history'] = float(np.max(np.abs(np.array(r['after_preparation_qpos'])-group[0]['after_preparation_qpos'])))
            r['max_observed_gripper_delta_from_no_history'] = float(np.max(np.abs(
                np.array(r['after_preparation_observed_gripper'])-group[0]['after_preparation_observed_gripper'])))
    result = {'rows': rows, 'training': False, 'gpu_used': False, 'complete_reference': args.complete_reference,
        'scope': 'CPU two-control preparation only, no cameras or VLA; different preceding histories; no relabeling'}
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps([{k:v for k,v in r.items() if 'qpos' not in k or k.startswith('max_')} for r in rows]))


if __name__ == '__main__':
    main()
