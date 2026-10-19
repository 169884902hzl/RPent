"""Read final private object/contact geometry from saved branch endpoints only."""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def read_ref(reference):
    data = Path(reference['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != reference['sha256']:
        raise ValueError('registered artifact changed: '+reference['path'])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    spec = importlib.util.spec_from_file_location('launcher',
        args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.bootstrap_source('d2')
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero import v5_branch_state

    rows = []
    for root in args.root:
        for path in sorted(root.resolve(strict=True).glob('N*/*/*/replay/summary.json')):
            trial = json.loads(path.read_bytes())
            assignment = json.loads((path.parents[2]/'assignment.json').read_bytes())
            case = assignment['case']
            saved = pickle.loads(read_ref(trial['endpoint']))
            physics = saved['physics']
            env = v5_branch_state.attach_branch_state(ControlEnv(
                bddl_file_name=case['bddl']['path'], has_renderer=False,
                has_offscreen_renderer=False, use_camera_obs=False, camera_names=[],
                ignore_done=True, hard_reset=False, horizon=10015))
            try:
                env.seed(case['episode']['seed'])
                env.reset()
                env.set_init_state(physics['sim_state'])
                # No camera/observable replay is claimed: this CPU analysis
                # only needs restored physical geometry and makes no control.
                actuators = copy.deepcopy(physics['actuator_state'])
                actuators.pop('observation_state', None)
                v5_branch_state.restore_actuators(env, actuators)
                state_error = float(np.max(np.abs(np.asarray(env.get_sim_state())
                    - np.asarray(physics['sim_state']))))
                if state_error != 0.:
                    raise RuntimeError(f'physical endpoint state differs by {state_error}')
                robot = env.env.robots[0]
                site = robot.eef_site_id
                if isinstance(site, dict):
                    if len(site) != 1:
                        raise ValueError('diagnostic expects one Panda end effector')
                    site = next(iter(site.values()))
                eef = np.asarray(env.env.sim.data.site_xpos[site])
                contacts = env.v5_grasp_contacts()
                objects = sorted([{'symbol': name,
                    'body_origin_xyz_m': value['xyz'],
                    'distance_to_eef_m': float(np.linalg.norm(np.asarray(value['xyz'])-eef)),
                    'dual_finger_contact': value['dual_finger_contact']}
                    for name, value in contacts['objects'].items()],
                    key=lambda value: (value['distance_to_eef_m'], value['symbol']))
                source = trial['subtask']['source_symbol']
                row = {'case': case['episode'], 'sampling_seed': trial['trial_seed'],
                    'variant': case['diagnostic']['variant'], 'summary': str(path),
                    'endpoint': trial['endpoint'], 'private_endpoint_success': trial['success'],
                    'stop_reason': trial['reason'], 'eef_xyz_m': eef.tolist(),
                    'source_symbol': source,
                    'source_at_endpoint': next((value for value in objects if value['symbol'] == source), None),
                    'nearest_objects': objects[:5],
                    'dual_finger_objects': [value['symbol'] for value in objects if value['dual_finger_contact']],
                    'contacts': contacts['contacts'], 'physical_state_max_error': state_error,
                    'reference': 'actual body origins after handoff; not initial public centres or shape-surface distances',
                    'physics_steps': 0, 'training': False, 'model_visible': False}
                rows.append(row)
                print(json.dumps({key: row[key] for key in
                    ('case', 'sampling_seed', 'variant', 'source_at_endpoint', 'nearest_objects')}), flush=True)
            finally:
                env.close()
    report = {'source_snapshot': str(args.source.resolve()),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'rows': rows, 'physics_steps': 0, 'gpu_used': False, 'training': False,
        'scope': 'private postprocessing only; no sensor phase equivalence or earlier success-time claim'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
