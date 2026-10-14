"""Submit physical starts only for completed, pinned changed-goal geometry."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_public_references_20261009_r1'
ADAPTER = ROOT / 'coordination/perturb_public_reference_adapter_20261009_r1'
GEOMETRY = ROOT / 'results/harness_v5/perturb_changed_goal_geometry_20261009_r6'
OUTPUT = ROOT / 'results/harness_v5/perturb_changed_goal_selection_20261009_r2'
BASE = ROOT / 'results/harness_v5/perturb_skill_selection_20261009_r1'


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    launcher = ADAPTER / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    producer = ADAPTER / 'scripts/prepare_v5_perturb_skill_selection_20261009.py'
    for manifest in sorted(GEOMETRY.glob('*/manifest.json')):
        cell = manifest.parent.name.removeprefix('selection_')
        prep = OUTPUT / cell / 'preparation'
        if (prep / 'startup_submission.json').exists():
            print(json.dumps({'cell': cell, 'status': 'startup_already_submitted'}))
            continue
        materialized = json.loads(manifest.read_text())
        if materialized['changed_goal_valid'] < 100 or any(
                r['status'] == 'preparation_error' for r in materialized['rows']):
            print(json.dumps({'cell': cell, 'status': 'preparation_incomplete_or_error'}))
            continue
        if not all(row.get('changed_goal') for row in materialized['rows'] if row['status'] == 'prepared'):
            raise ValueError('changed-goal pool must actually change every selected goal')
        pool_ref = materialized['pool']
        pool_path = Path(pool_ref['path'])
        if ref(pool_path) != pool_ref:
            raise ValueError('preregistered pool changed')
        declared = {row['rule']['layout_seed']: row for row in json.loads(pool_path.read_text())['records']}
        for row in materialized['rows']:
            record = declared[row['layout_seed']]
            if row['rule_sha256'] != record['rule_sha256']:
                raise ValueError('preparation rule differs from preregistration')
            row['name'] = record['name']
        compatible = OUTPUT / 'geometry_views' / (cell + '.json')
        compatible.parent.mkdir(parents=True, exist_ok=True)
        with compatible.open('x') as stream:
            stream.write(json.dumps({**materialized, 'name_restore_source': ref(manifest),
                                     'physical_state_bytes_changed': False}, indent=2) + '\n')
        base = BASE / cell / 'preparation/selection.json'
        base_plan = json.loads(base.read_text())
        budget_ref = base_plan['references'][1]
        budget_path = Path(budget_ref['path'])
        if ref(budget_path) != budget_ref or 'budget' not in json.loads(budget_path.read_text()):
            raise ValueError('registered original budget plan changed or lacks its budget')
        command = [str(ROOT / '.venv/bin/python'), str(producer), '--materialized', str(compatible),
                   '--materialized-sha256', ref(compatible)['sha256'], '--base-plan', str(budget_path),
                   '--source', str(SOURCE), '--adapter', str(ADAPTER),
                   '--choice-package', base_plan['choice_package'], '--output', str(prep)]
        env = {**os.environ, 'PYTHONPATH': f'{ADAPTER}:{SOURCE}:{SOURCE / "scripts"}', 'LIBERO_TYPE': 'standard'}
        made = subprocess.run(command, env=env, text=True, capture_output=True)
        if prep.exists():
            (prep / 'plan_preparation.log').write_text(made.stdout + made.stderr)
        made.check_returncode()
        plan_path = prep / 'selection.json'
        plan = json.loads(plan_path.read_text())
        if len(plan['cases']) != 100 or not all(case['changed_goal'] for case in plan['cases']):
            raise ValueError('exactly100 declared changed-goal cases required')
        values = {'PERTURB_SKILL_PLAN': str(plan_path), 'PERTURB_SKILL_PLAN_SHA': ref(plan_path)['sha256'],
                  'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(ADAPTER),
                  'PERTURB_SKILL_OUTPUT': str(OUTPUT / cell), 'PERTURB_SKILL_STARTUP': '1'}
        cpu = subprocess.run(['bash', str(launcher)], env={**env, **values, 'PERTURB_SKILL_CPU_ONLY': '1'},
                             capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        command = ['sbatch', '--parsable', '--array=0',
                   '--export=ALL,' + ','.join(k + '=' + v for k, v in values.items()), str(launcher)]
        job = subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()
        record = {'job': job, 'environment': values, 'launcher': ref(launcher), 'manifest': ref(plan_path),
                  'CPU_preflight': 'pass', 'physical_startup': 'pending', 'confirmation': False}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'cell': cell, 'job': job, 'cases': len(plan['cases']), 'CPU_preflight': 'pass'}), flush=True)


if __name__ == '__main__':
    main()
