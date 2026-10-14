"""Pin stationary negative-evidence queries and start selection diagnostics."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT/'source_v5_grasp_public_pose_r6_20261010_r1'
SOURCE = ROOT/'source_v5_grasp_public_tracking_r7_20261010_r1'
ADAPTER = ROOT/'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT/'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
OUT = ROOT/'results/harness_v5/public_grasp_tracking_r7_selection_20261010'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


shutil.copytree(PARENT, SOURCE, symlinks=True,
    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
for origin, target in [('public_grasp_tracking_r7_staging.py', 'robots/libero/v5_grasp_public_tracking.py'),
                       ('test_public_grasp_tracking_r7_staging.py', 'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py')]:
    shutil.copyfile(ROOT/'coordination'/origin, SOURCE/target)
env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
check = subprocess.run([str(ROOT/'.venv/bin/python'), '-m', 'pytest',
    'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
    'tests/unit_tests/robots/libero/test_v5_category_contact_anchor.py',
    'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py', '-q'],
    cwd=SOURCE, env=env, text=True, capture_output=True)
(SOURCE/'CPU_public_tracking_r7.log').write_text(check.stdout+check.stderr)
check.check_returncode()
identity = json.loads((PARENT/'source_identity_v3r9.json').read_text())
identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
    purpose='fresh stationary negative evidence for unique known source; private locked v3 unchanged',
    public_tracking_source=pin(SOURCE/'robots/libero/v5_grasp_public_tracking.py'),
    CPU_validation={'command': check.args, 'output': check.stdout})
for record in identity['files']:
    record.update(pin(SOURCE/record['relative_path']))
(SOURCE/'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2)+'\n')
archive = SOURCE.with_suffix('.tar')
with tarfile.open(archive, 'w') as stream:
    for child in SOURCE.iterdir():
        if child.name not in ('__pycache__', '.pytest_cache'):
            stream.add(child, arcname=child.name)
archive_pin = {**pin(archive), 'archive_complete': True}
for name, category in [('bottle_pi05_stationary', 'bottle'), ('cup_pi05_stationary', 'cup')]:
    base = ROOT/f'results/harness_v5/perturb_contact_methods_selection_20261009_r3/grasp_{category}_pi05/preparation/selection.json'
    plan = copy.deepcopy(json.loads(base.read_text()))
    if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
        raise ValueError('original selection100 required')
    plan.update(source_path=str(SOURCE), adapter_path=str(ADAPTER), source_commit=identity['snapshot_id'],
        source_snapshot={**identity, 'path': str(SOURCE), 'commit': identity['snapshot_id'], 'archive': archive_pin},
        parent_plan=pin(base), qualification_authorized=False,
        purpose='original perturbation selection: stationary fresh RGB-D negative evidence, no private control input',
        new_evidence_replay=True, new_training_rows=0)
    for record in plan['producer_dependencies']:
        old = Path(record['path'])
        new = ADAPTER/'scripts'/old.name
        if '/scripts/' in str(old) and 'adapter_' in str(old) and new.exists():
            record.update(pin(new))
    for condition in plan['conditions'].values():
        condition.setdefault('overrides', {}).update(grasp_public_tracking_v1=True,
            grasp_public_coupled_lift_v1=True, grasp_independent_views_v1=True)
    for case in plan['cases']:
        case['name'] += '_public_tracking_r7'
    prep = OUT/name/'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    path = prep/'selection.json'
    path.write_text(json.dumps(plan, indent=2)+'\n')
    task_env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    cpu = subprocess.run(['bash', str(LAUNCH)], env=task_env, text=True, capture_output=True)
    (prep/'CPU_preflight.log').write_text(cpu.stdout+cpu.stderr)
    cpu.check_returncode()
    task_env['PERTURB_SKILL_CPU_ONLY'] = '0'
    job = subprocess.run(['sbatch', '--parsable', '--export=ALL', str(LAUNCH)],
        env=task_env, text=True, capture_output=True, check=True).stdout.strip()
    receipt = {'name': name, 'startup_job': job, 'plan': pin(path), 'launcher': pin(LAUNCH),
               'CPU_preflight': cpu.stdout, 'qualification_allowed': False}
    (prep/'submission.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
