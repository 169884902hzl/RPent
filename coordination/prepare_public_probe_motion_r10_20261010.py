"""Replay the observed undershoot with unchanged public translation criterion."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_inner_pad_r9_20261010_r1'
SOURCE = ROOT / 'source_v5_grasp_public_probe_motion_r10_20261010_r1'
STAGING = ROOT / 'coordination/public_probe_motion_r10_staging'
BASE = ROOT / 'results/harness_v5/public_grasp_inner_pad_r9_selection_20261010_r1'
OUT = ROOT / 'results/harness_v5/public_grasp_probe_motion_r10_selection_20261010_r1'
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
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    original = 'self.move(target, 1., recoverable=True, tolerance_m=.015)'
    if body.count(original) != 1:
        raise ValueError('unexpected public probe move layout')
    runtime.write_text(body.replace(original, 'self.move(target, 1., recoverable=True, tolerance_m=.004)'))
    env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py',
        'tests/unit_tests/robots/libero/test_v5_category_contact_anchor.py'],
        env=env, cwd=SOURCE, capture_output=True, text=True)
    (SOURCE / 'CPU_probe_motion_r10.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
                    purpose='make the 4cm public active probe exceed the unchanged 3cm required measured translation; private truth unchanged',
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
    for name in ('bottle_pi05',):
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
                    purpose='development regression of short public probe; no new verifier threshold; no confirmation qualification',
                    new_evidence_replay=True, new_training_rows=0)
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if str(path) == prior_producer:
                record.update(pin(producer))
            elif path.is_relative_to(PARENT):
                record.update(pin(SOURCE / path.relative_to(PARENT)))
        for case in plan['cases']:
            case['name'] = case['name'].replace('_public_inner_pad_r9', '_public_probe_motion_r10')
        regression = 'selection_grasp_bottle_9301104_pi05_public_probe_motion_r10'
        matches = [case for case in plan['cases'] if case['name'] == regression]
        if len(matches) != 1:
            raise ValueError('exact failing development regression case missing')
        plan['cases'] = matches + [case for case in plan['cases'] if case['name'] != regression]
        plan['startup_regression_case'] = regression
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
