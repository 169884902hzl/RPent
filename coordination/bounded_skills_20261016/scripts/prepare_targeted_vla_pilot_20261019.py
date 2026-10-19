"""Pin one old failure and one success for the narrow-monitor consistency pilot."""
import argparse
import os
import subprocess
from pathlib import Path

from prepare_hybrid_repair_20261019 import BASE, ROOT, CALIBRATION, read, ref, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--grasp-calibration', type=Path, default=CALIBRATION)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    registry = BASE/'preparation/D2_handoff_six_20261019.json'
    cases = []
    for seed in (17401000, 13402000):
        selected = next(row for row in read(registry)['rows'] if row['seed'] == seed)
        summary = Path(selected['raw_summary'])
        original = read(summary.parents[3]/'assignment.json')['case']
        cases.append({**original, 'name': original['name']+'_targeted_scope_r'+str(seed),
            'grasp_measurement_calibration': ref(args.grasp_calibration),
            'diagnostic': {'kind': 'replay', 'domain': 'd2', 'variant': 'targeted_scope',
                'old_summary': ref(summary), 'branchpoint': ref(Path(selected['branchpoint'])),
                'targeted_vla_measurement_v1': True, 'migrate_v3_header_to_v4': True,
                'budget': {'blocks': 24, 'no_progress_blocks': 3, 'controls_per_check': 1,
                    'minimum_progress_m': .005, 'max_controls': None}}})
    directory = ROOT/'results/bounded_skills/targeted_vla_pilot_20261019'/args.commit[:8]/'preparation'
    directory.mkdir(parents=True)
    manifest = directory/'manifest.json'
    write(manifest, {'evaluation': 'hybrid_repair', 'source_commit': args.commit,
        'cases': cases, 'training': False, 'confirmation': False,
        'registry': ref(registry), 'scope': 'two fixed old branches (one success, one failure); monitor consistency/timing only, no success-rate estimate'})
    batch = {'domain': 'd2', 'source': str(source), 'source_commit': args.commit,
        'manifest': ref(manifest), 'indices': [0, 1]}
    plan = {'selected_n': 2, 'batches': [batch], 'training': False, 'confirmation': False}
    write(directory/'batch_plan.json', plan)
    script = ROOT/'launcher_shared_20261019_3fa8bb8f1740/shared_gpu_episodes_20261019.py'
    command = [str(ROOT/'.venv/bin/python'), str(script), '--batch-plan',
        str(directory/'batch_plan.json'), '--batch-index', '0', '--preflight']
    checked = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
        env=dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),
            OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
    (directory/'preflight.log').write_text(checked.stdout+checked.stderr)
    checked.check_returncode()
    report = {'source': str(source), 'source_commit': args.commit, 'manifest': ref(manifest),
        'batch_plan': ref(directory/'batch_plan.json'), 'launcher': ref(script),
        'preflight': {'exit_code': 0, 'command': command}, 'submitted': False, 'training': False}
    write(directory/'preparation.json', report)
    print(report)


if __name__ == '__main__':
    main()
