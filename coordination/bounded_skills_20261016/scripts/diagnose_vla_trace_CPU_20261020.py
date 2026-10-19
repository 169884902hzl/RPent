"""Replay recorded controls on CPU, then privately score observed v3 windows."""

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def checked(reference):
    raw = Path(reference['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('registered replay input changed')
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
        MKL_NUM_THREADS='1', LIBERO_TYPE='pro',
        LIBERO_GRASP_DIAGNOSTIC_MODELS=str(args.output.resolve().parent/'trace_CPU_private_models'))
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location('launcher', source/
        'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.bootstrap_source('d2')
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv

    from robots.libero import v5_branch_state
    from robots.libero.v5_grasp_truth import (
        V3_MIN_SAMPLES, _integration_state, contact_sample,
        enrich_registered_samples, sustained_grasp_v3,
    )

    trial = json.loads(args.summary.read_bytes())
    assignment = json.loads((args.summary.parents[2]/'assignment.json').read_bytes())
    case = assignment['case']
    start = pickle.loads(checked(case['diagnostic']['branchpoint']))['physics']
    end = pickle.loads(checked(trial['endpoint']))['physics']
    execution = next(row['execution'] for line in checked(trial['choices']).splitlines()
        for row in json.loads(line)['execution_details']
        if 'skill_stop_reason' in row.get('execution', {}))
    reference = json.loads(checked(trial['evidence']))['reference']
    name = trial['subtask']['source_symbol']
    env = v5_branch_state.attach_branch_state(ControlEnv(bddl_file_name=case['bddl']['path'],
        has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False, camera_names=[],
        ignore_done=True, hard_reset=False, horizon=10015))
    samples, states, phases, errors = [], [], [], []
    try:
        env.seed(case['episode']['seed'])
        env.reset()
        env.set_init_state(start['sim_state'])
        actuators = copy.deepcopy(start['actuator_state'])
        actuators.pop('observation_state', None)
        v5_branch_state.restore_actuators(env, actuators)
        for phase, trace in [('preparation', execution['preparation'].get('trace', [])),
                ('pi05', execution['trace']), ('handoff', execution['handoff'].get('trace', []))]:
            for index, row in enumerate(trace):
                env.step(np.asarray(row['action']))
                robot = env.env.robots[0]
                site = robot.eef_site_id
                site = next(iter(site.values())) if isinstance(site, dict) else site
                error = float(np.max(np.abs(env.env.sim.data.site_xpos[site]-row['after']['eef_xyz_m'])))
                errors.append(error)
                if error > 1e-8:
                    raise RuntimeError(f'control replay differs: {phase}:{index+1}, {error}m')
                samples.append(contact_sample(env.env, name))
                states.append(_integration_state(env.env))
                phases.append({'phase': phase, 'control': index+1})
        final_error = float(np.max(np.abs(np.asarray(env.get_sim_state())-end['sim_state'])))
        if final_error > 1e-8:
            raise RuntimeError(f'endpoint replay differs: {final_error}')
        # No private label is calculated until trajectory identity is checked.
        enrich_registered_samples(env.env, name, reference, samples, states)
        windows = []
        for at in range(V3_MIN_SAMPLES, len(samples)+1):
            truth = sustained_grasp_v3(samples[at-V3_MIN_SAMPLES:at], reference)
            windows.append({'start': phases[at-V3_MIN_SAMPLES], 'end': phases[at-1],
                'success': truth['success']})
        report = {'summary': str(args.summary.resolve()), 'source': str(source),
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'sampling_seed': trial['trial_seed'], 'controls': len(execution['trace']),
            'recorded_endpoint_success': trial['success'], 'recorded_stop': trial['reason'],
            'max_recorded_eef_error_m': max(errors, default=0.),
            'final_physics_error': final_error, 'first_observed_v3_success_window':
                next((row for row in windows if row['success'] is True), None),
            'known_success_windows': sum(row['success'] is True for row in windows),
            'unknown_windows': sum(row['success'] is None for row in windows),
            'windows': windows, 'sample_phases': phases, 'samples': samples,
            'gpu_used': False, 'training': False, 'model_visible': False,
            'scope': 'private replay labels along the already executed controls; no invented earlier hold probes or rescoring of closed confirmation data'}
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({k: report[k] for k in ('sampling_seed', 'controls',
            'max_recorded_eef_error_m', 'final_physics_error', 'first_observed_v3_success_window',
            'known_success_windows', 'unknown_windows')}))
    finally:
        env.close()


if __name__ == '__main__':
    main()
