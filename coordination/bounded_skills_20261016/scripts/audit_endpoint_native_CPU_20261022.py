"""Read saved evaluation endpoints without stepping or changing old scores."""
import argparse
import copy
import json
import os
from pathlib import Path
import pickle
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022/D2_option_fallback_a3c7cf43'
    sys.path.insert(0, str(args.source))
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro', MUJOCO_GL='egl',
        PYOPENGL_PLATFORM='egl', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    import robots.libero.env_server
    import rlinf.envs.libero.libero_env
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.v5_branch_state import restore_actuators, native_data_state

    rows, scanned = [], 0
    for budget in range(3):
        for path in sorted((base/f'D2_recovery{budget}').glob('case*/summary.json')):
            summary = json.loads(path.read_bytes())
            pending = []
            for stage in summary.get('subtasks', []):
                for trial in stage['trials']:
                    if trial['success'] is not False:
                        continue
                    physics = pickle.loads(Path(trial['endpoint']['path']).read_bytes())['physics']
                    scanned += 1
                    if physics.get('native_success_event_count', 0):
                        pending.append((trial, physics))
            if not pending:
                continue
            env = ControlEnv(bddl_file_name=summary['case']['bddl']['path'],
                use_camera_obs=False, has_renderer=False, has_offscreen_renderer=False,
                camera_names=[], ignore_done=True, horizon=10015)
            try:
                env.reset()
                for trial, physics in pending:
                    env.set_init_state(physics['sim_state'])
                    saved = copy.deepcopy(physics['actuator_state'])
                    saved.pop('observation_state', None)
                    restore_actuators(env, saved)
                    exact = native_data_state(env)['sha256'] == physics['actuator_state']['native_data']['sha256']
                    if not exact:
                        raise ValueError('native endpoint restore differs: '+trial['endpoint']['path'])
                    rows.append({'case': summary['case']['name'], 'recovery_budget': budget,
                        'subtask': trial['subtask']['id'], 'method': trial['method'],
                        'variant': trial.get('vla_variant'), 'seed': trial['trial_seed'],
                        'local_success': trial['success'],
                        'native_task_success_at_endpoint': bool(env.env._check_success()),
                        'native_data_byte_identical': exact, 'sim_controls_executed': 0,
                        'original_trial_endpoint': trial['endpoint'], 'parent_summary': str(path)})
            finally:
                env.close()
    args.output.mkdir(exist_ok=False, parents=True)
    result = {'failed_local_trials_scanned': scanned, 'native_event_shortlist': len(rows),
        'native_complete_local_false': sum(r['native_task_success_at_endpoint'] for r in rows),
        'cases': sorted({r['case'] for r in rows if r['native_task_success_at_endpoint']}),
        'rows': rows, 'old_scores_unchanged': True, 'training': False,
        'scope': 'CPU endpoint predicate check, no physics controls; native events used only to shortlist'}
    (args.output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__ == '__main__':
    main()
