"""Pin original failed-category forks; startup must precede full submission."""
import argparse
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

from prepare_hybrid_repair_20261019 import ROOT, BASE, read, ref, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--baseline-report', type=Path, required=True)
    parser.add_argument('--submit-startup', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    baseline = read(args.baseline_report)
    assert baseline['source_commit'] == 'ec89f74' and not baseline['worker_errors']
    original = read(BASE/'reports/original20_support_roundrobin_20261018_full_submission.json')
    manifest = Path(original['manifest']['path'])
    assert ref(manifest) == original['manifest']
    cohort = read(manifest)
    selected = {'microwave_open', 'microwave_close', 'plate_push'}
    failed_cups = {r['result']['case']['name'] for r in baseline['records']
        if r['result']['case']['category'] == 'cup_transfer' and not r['result']['success']}
    assert len(failed_cups) == 11
    cases = []
    for case in cohort['cases']:
        if case['category'] not in selected and case['name'] not in failed_cups:
            continue
        mode = {'microwave_open': 'open', 'microwave_close': 'close',
            'plate_push': 'push', 'cup_transfer': 'pick'}[case['category']]
        controls = {'libero_90': 400, 'libero_goal': 300, 'libero_10': 520}[case['episode']['suite']]
        cases.append({**case, 'diagnostic': {'kind': 'original_fork', 'domain': 'original',
            'subtask_mode': mode, 'trial_seed_base': 20500000+10000*len(cases),
            'budget': {'blocks': math.ceil(controls/5), 'no_progress_blocks': None,
                'controls_per_check': 1, 'minimum_progress_m': .005, 'max_controls': controls}}})
    assert len(cases) == 71
    directory = ROOT/'results/bounded_skills/original_hybrid_forks_20261019'/args.commit[:8]/'preparation'
    directory.mkdir(parents=True)
    pinned = directory/'manifest.json'
    write(pinned, {'evaluation': 'hybrid_repair', 'source_commit': args.commit, 'cases': cases,
        'training': False, 'confirmation': False, 'baseline': ref(args.baseline_report),
        'original_cohort': ref(manifest), 'permanent_exclusions': cohort['permanent_exclusions'],
        'selection': 'all20 microwave open, all20 close, all20 plate push; exactly11 failed cup states from pinned original220',
        'budget_scope': 'exploratory no-progress-off; original suite evaluation-scale total control budget; not final stop-rule choice',
        'scope': 'original40/90 subtask development forks; no D2/PRO/training or whole-episode success claim'})
    batch = {'domain': 'original', 'source': str(source), 'source_commit': args.commit,
        'manifest': ref(pinned)}
    batches = [{**batch, 'indices': list(range(i, min(i+8, len(cases))))}
        for i in range(0, len(cases), 8)]
    full = {'selected_n': 8, 'batches': batches, 'training': False, 'confirmation': False}
    startup_indices = [next(i for i, c in enumerate(cases) if c['diagnostic']['subtask_mode'] == mode)
        for mode in ('open', 'close', 'push', 'pick')]
    startup = {**full, 'batches': [{**batch, 'indices': startup_indices}]}
    write(directory/'batch_plan.json', full)
    write(directory/'startup_plan.json', startup)
    script = source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    launcher = ROOT/('launcher_shared_20261019_'+ref(script)['sha256'][:12])
    launcher.mkdir(exist_ok=True)
    for name in (script.name, 'run_shared_batch_20261019.sbatch'):
        target = launcher/name
        if target.exists():
            assert target.read_bytes() == (script.parent/name).read_bytes()
        else:
            shutil.copy2(script.parent/name, target)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    preflights = []
    for name, plan in (('startup', startup), ('batch', full)):
        for index in range(len(plan['batches'])):
            command = [str(ROOT/'.venv/bin/python'), str(launcher/script.name),
                '--batch-plan', str(directory/(name+'_plan.json')), '--batch-index', str(index), '--preflight']
            checked = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
            log = directory/f'{name}_{index}_preflight.log'
            log.write_text(checked.stdout+checked.stderr)
            checked.check_returncode()
            preflights.append({'command': command, 'exit_code': 0, 'log': str(log)})
    report = {'source_commit': args.commit, 'source': str(source), 'manifest': ref(pinned),
        'launcher': ref(launcher/script.name), 'preflights': preflights,
        'preparation': str(directory), 'training': False, 'confirmation': False,
        'production_submitted': False, 'cases': len(cases), 'startup_indices': startup_indices}
    write(directory/'preparation.json', report)
    if args.submit_startup:
        submit_env = dict(os.environ, BATCH_PLAN=str(directory/'startup_plan.json'),
            LAUNCHER=str(launcher/script.name), STARTUP='1', RESULTS_ROOT=str(directory.parent))
        command = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=0%1',
            '--export=ALL', str(launcher/'run_shared_batch_20261019.sbatch')]
        job = subprocess.check_output(command, cwd=ROOT, env=submit_env, text=True).strip().split(';')[0]
        report = {**report, 'job': job, 'command': command, 'startup': True}
        write(directory/'startup_submission.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
