"""Measure a zero-increment OSC handoff on the six saved physical endpoints."""
import argparse
import copy
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro')
    sys.path.insert(0, str(args.source))
    spec = importlib.util.spec_from_file_location('launcher', Path(__file__).with_name('shared_gpu_episodes_20261019.py'))
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.bootstrap_source('d2')
    launcher.install_d2_restore_compatibility()
    import numpy as np
    from scipy.spatial.transform import Rotation
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero import v5_branch_state
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    from robots.libero.bounded_motion import measured_robot, public_control

    output = []
    for row in json.loads(args.manifest.read_bytes())['rows']:
        record = json.loads(Path(row['raw_summary']).read_bytes())
        assignment = json.loads(Path(row['raw_summary']).parents[3].joinpath('assignment.json').read_bytes())
        case = assignment['case']
        saved = pickle.loads(Path(row['endpoint']['path']).read_bytes())
        physics = saved['physics']
        env = v5_branch_state.attach_branch_state(ControlEnv(bddl_file_name=case['bddl']['path'],
            has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False, camera_names=[],
            ignore_done=True, hard_reset=False, horizon=10015))
        try:
            env.seed(case['episode']['seed'])
            env.reset()
            env.set_init_state(physics['sim_state'])
            observation = v5_branch_state.restore_actuators(env, physics['actuator_state'])
            actual = copy.deepcopy(physics)
            actual.update(sim_state=env.get_sim_state(), actuator_state=v5_branch_state.actuator_state(env))
            exact_restore = snapshot_digest(actual) == snapshot_digest(physics)
            assert exact_restore
            def step(action):
                nonlocal observation
                observation = env.step(action)[0]
            p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: observation), _step_env=step)
            initial = measured_robot(p)
            grip = saved['public_runtime']['adapter']['gripper_command']
            action = np.r_[np.zeros(6), grip]
            trace, stable = [], 0
            for index in range(30):
                before, after = public_control(p, action)
                velocity = float(np.linalg.norm(np.array(after['eef_xyz_m'])-before['eef_xyz_m'])*20)
                angular = float((Rotation.from_quat(after['eef_quat_xyzw'])
                    * Rotation.from_quat(before['eef_quat_xyzw']).inv()).magnitude()*20)
                stable = stable+1 if velocity <= .005 and angular <= .02 else 0
                trace.append({'step': index+1, 'velocity_m_s': velocity,
                    'angular_velocity_rad_s': angular, 'before': before, 'after': after})
                if stable >= 4:
                    break
            private = json.loads(Path(row['truth_record']).read_bytes())
            archive = args.output.parent / (args.output.stem+'_private_models')
            os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS'] = str(archive.resolve())
            truth = env.v5_measure_grasp_hold(row['source_symbol'], private['reference'])
            result = {'case': row['case'], 'seed': row['seed'], 'exact_restore': exact_restore,
                'old_truth': record['success'], 'hold_truth': truth['truth_v3']['success'],
                'hold_truth_status': truth['truth_v3']['status'], 'settled': stable >= 4,
                'steps': len(trace), 'max_drift_m': max(float(np.linalg.norm(
                    np.array(x['after']['eef_xyz_m'])-initial['eef_xyz_m'])) for x in trace),
                'final_speed_m_s': trace[-1]['velocity_m_s'], 'trace': trace}
            output.append(result)
            print(json.dumps({k:v for k,v in result.items() if k != 'trace'}), flush=True)
        finally:
            env.close()
    with args.output.open('x') as stream:
        json.dump({'scope':'six saved endpoints; CPU simulation, no RGB-D refresh or VLA inference; development diagnostic only',
            'training':False, 'gpu_used':False, 'rows':output}, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
