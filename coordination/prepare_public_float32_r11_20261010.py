"""Replay selection cases with public RGB-D precision preserved; no rule change."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_probe_motion_r10_20261010_r1'
SOURCE = ROOT / 'source_v5_grasp_public_float32_r11_20261010_r2'
STAGING = ROOT / 'coordination/public_float32_r11_staging'
BASE = ROOT / 'results/harness_v5/public_grasp_inner_pad_r9_selection_20261010_r1'
OUT = ROOT / 'results/harness_v5/public_grasp_float32_r11_selection_20261010_r2'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('tests/unit_tests/robots/libero/test_libero_observation_precision.py',):
        shutil.copyfile(STAGING / relative, SOURCE / relative)
    tools_path = SOURCE / 'robots/libero/tools.py'
    body = tools_path.read_text()
    if body.count(').astype(np.float16)') != 2:
        raise ValueError('unexpected high-resolution world-map casts')
    tools_path.write_text(body.replace(').astype(np.float16)', ').astype(np.float32)'))
    env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_libero_observation_precision.py',
        'tests/unit_tests/robots/libero/test_libero_toolkit_contracts.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'],
        env=env, cwd=SOURCE, capture_output=True, text=True)
    (SOURCE / 'CPU_public_float32_r11.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
                    purpose='preserve public high-resolution RGB-D in FP32; no success threshold change',
                    public_observation_source=pin(SOURCE / 'robots/libero/tools.py'),
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
                    purpose='development regression of public RGB-D quantization; no confirmation qualification',
                    new_evidence_replay=True, new_training_rows=0)
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if str(path) == prior_producer:
                record.update(pin(producer))
            elif path.is_relative_to(ROOT / 'source_v5_grasp_public_inner_pad_r9_20261010_r1'):
                record.update(pin(SOURCE / path.relative_to(ROOT / 'source_v5_grasp_public_inner_pad_r9_20261010_r1')))
        for case in plan['cases']:
            case['name'] = case['name'].replace('_public_inner_pad_r9', '_public_float32_r11')
        if name == 'bottle_analytic':
            regression = 'selection_grasp_bottle_9301109_analytic_public_float32_r11'
            matches = [case for case in plan['cases'] if case['name'] == regression]
            if len(matches) != 1:
                raise ValueError('exact development regression missing')
            plan['cases'] = matches + [case for case in plan['cases'] if case['name'] != regression]
            plan['startup_regression_case'] = regression
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        task_env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
                        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
                        PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1',
                        PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCH)], env=task_env, cwd='/tmp', capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        task_env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--nice=1000', '--export=ALL', str(LAUNCH)],
                                   env=task_env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
                   'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout,
                   'qualification_allowed': False, 'private_truth_rule_unchanged': True,
                   'public_rgbd_storage_dtype': 'float32', 'public_verdict_rule_unchanged': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
