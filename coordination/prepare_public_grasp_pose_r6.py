"""Pin the public wrist-pose query fix and compare it on original selection states."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_grasp_public_pose_r6_20261010_r1'
PARENT = ROOT / 'source_v5_grasp_truth_v3r9_20261010_r2'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
OUT = ROOT / 'results/harness_v5/public_grasp_pose_r6_selection_20261010'


def pin(p):
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
                purpose='public wrist pose segmentation hint; locked private v3 truth unchanged',
                public_pose_change=pin(ROOT / 'coordination/grasp_public_pose_r6_20261010.patch'),
                CPU_validation={'targeted_remote': '49 passed', 'targeted_local': '42 passed'})
for record in identity['files']:
    record.update(pin(SOURCE / record['relative_path']))
(SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
archive = SOURCE.with_suffix('.tar')
with tarfile.open(archive, 'w') as stream:
    for child in SOURCE.iterdir():
        if child.name not in ('__pycache__', '.pytest_cache'):
            stream.add(child, arcname=child.name)
archive_pin = {**pin(archive), 'archive_complete': True}
for name, parent in [('bottle_pi05_pose', 'perturb_contact_methods_selection_20261009_r3/grasp_bottle_pi05'),
                     ('cup_pi05_pose', 'perturb_contact_methods_selection_20261009_r3/grasp_cup_pi05')]:
    base = ROOT / 'results/harness_v5' / parent / 'preparation/selection.json'
    plan = copy.deepcopy(json.loads(base.read_text()))
    if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
        raise ValueError('fixed original selection100 required; no confirmation-state tuning')
    plan.update(source_path=str(SOURCE), adapter_path=str(ADAPTER), source_commit=identity['snapshot_id'],
        source_snapshot={**identity, 'path': str(SOURCE), 'commit': identity['snapshot_id'], 'archive': archive_pin},
        parent_plan=pin(base), qualification_authorized=False,
        purpose='original perturbation selection: rotated public query envelope; no private control input',
        new_evidence_replay=True, new_training_rows=0)
    for rec in plan['producer_dependencies']:
        old = Path(rec['path'])
        new = ADAPTER / 'scripts' / old.name
        if '/scripts/' in str(old) and 'adapter_' in str(old) and new.exists():
            rec.update(pin(new))
    for condition in plan['conditions'].values():
        condition.setdefault('overrides', {}).update(grasp_public_tracking_v1=True,
            grasp_public_coupled_lift_v1=True, grasp_independent_views_v1=True)
    for c in plan['cases']:
        c['name'] += '_public_pose_r6'
    prep = OUT / name / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    check = subprocess.run(['bash', str(LAUNCH)], env=env, text=True, capture_output=True)
    (prep / 'CPU_preflight.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    job = subprocess.run(['sbatch', '--parsable', '--export=ALL', str(LAUNCH)],
        env=env, text=True, capture_output=True, check=True).stdout.strip()
    receipt = {'name': name, 'startup_job': job, 'plan': pin(path), 'launcher': pin(LAUNCH),
        'CPU_preflight': check.stdout, 'qualification_allowed': False}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
