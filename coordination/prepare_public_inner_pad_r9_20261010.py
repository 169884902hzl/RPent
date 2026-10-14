"""Measure inward pad faces on existing selection states; change no verdict."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_pad_r8_20261010_r1'
SOURCE = ROOT / 'source_v5_grasp_public_inner_pad_r9_20261010_r1'
STAGING = ROOT / 'coordination/public_inner_pad_r9_staging'
BASE = ROOT / 'results/harness_v5/public_grasp_pad_r8_selection_20261010_r3'
OUT = ROOT / 'results/harness_v5/public_grasp_inner_pad_r9_selection_20261010_r1'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('robots/libero/v5_grasp_public_tracking.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'):
        shutil.copyfile(STAGING / relative, SOURCE / relative)
    env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py',
        'tests/unit_tests/robots/libero/test_v5_category_contact_anchor.py'],
        env=env, cwd=SOURCE, capture_output=True, text=True)
    (SOURCE / 'CPU_inner_pad_r9.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
                    purpose='separate inward pad face evidence from outer/end faces; public verdict and private truth unchanged',
                    public_tracking_source=pin(SOURCE / 'robots/libero/v5_grasp_public_tracking.py'),
                    CPU_validation={'command': check.args, 'output': check.stdout})
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05'):
        old = BASE / name / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(old.read_text()))
        if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
            raise ValueError('registered selection100 only')
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        prior_producer = plan['producer']['path']
        plan.update(producer=pin(producer), source_path=str(SOURCE), source_commit=SOURCE.name,
                    source_snapshot={**identity, 'path': str(SOURCE), 'commit': SOURCE.name,
                                     'archive': {**pin(archive), 'archive_complete': True}},
                    parent_plan=pin(old), qualification_authorized=False,
                    purpose='original perturbation selection only; inward pad surface measurement; no new success threshold',
                    new_evidence_replay=True, new_training_rows=0)
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if str(path) == prior_producer:
                record.update(pin(producer))
            elif path.is_relative_to(PARENT):
                record.update(pin(SOURCE / path.relative_to(PARENT)))
        for case in plan['cases']:
            case['name'] = case['name'].replace('_public_pad_r8', '_public_inner_pad_r9')
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        task_env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
                        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
                        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1',
                        PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCH)], env=task_env, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        task_env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--nice=0', '--export=ALL', str(LAUNCH)],
                                   env=task_env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
                   'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout,
                   'qualification_allowed': False, 'verifier_verdict_unchanged': True,
                   'new_public_measurements_only': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
