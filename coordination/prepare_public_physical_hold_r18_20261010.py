"""Test actual 4 mm public probes and mandatory measured object co-motion."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_public_servo_coupling_r16_20261010_r1'
SOURCE = ROOT / 'source_v5_public_physical_hold_r18_20261010_r1'
STAGING = ROOT / 'coordination/public_physical_hold_r18_staging'
BASE = ROOT / 'results/harness_v5/public_servo_coupling_r16_selection_20261010_r1'
OUT = ROOT / 'results/harness_v5/public_physical_hold_r18_selection_20261010_r1'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise ValueError('source patch not unique: ' + old)
    return body.replace(old, new)


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('robots/libero/v5_grasp_public_tracking.py',
                     'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
                     'tests/unit_tests/robots/libero/test_v5_motion_trace.py'):
        shutil.copyfile(STAGING / Path(relative).name, SOURCE / relative)
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    body = replace_once(body, '        grasp_required_coupling_v1: bool = False,\n',
        '        grasp_required_coupling_v1: bool = False,\n        grasp_public_hold_v1: bool = False,\n')
    body = replace_once(body, '        self.grasp_required_coupling_v1 = grasp_required_coupling_v1\n',
        '        self.grasp_required_coupling_v1 = grasp_required_coupling_v1\n        self.grasp_public_hold_v1 = grasp_public_hold_v1\n')
    start = body.index('        self.last_verification_measurements["independent_grasp"] = {**paired, "measured_support": support}')
    end = body.index('    def _measure_grasp_pad_regions(', start)
    replacement = (STAGING / 'runtime_hold_block.txt').read_text()
    runtime.write_text(body[:start] + replacement + body[end:])
    evaluation = SOURCE / 'harness_v5_eval.py'
    body = evaluation.read_text()
    body = replace_once(body, '                             grasp_required_coupling_v1=getattr(args, "grasp_required_coupling_v1", False),\n',
        '                             grasp_required_coupling_v1=getattr(args, "grasp_required_coupling_v1", False),\n'
        '                             grasp_public_hold_v1=getattr(args, "grasp_public_hold_v1", False),\n')
    body = replace_once(body, '    parser.add_argument("--grasp-required-coupling-v1", action="store_true")\n',
        '    parser.add_argument("--grasp-required-coupling-v1", action="store_true")\n'
        '    parser.add_argument("--grasp-public-hold-v1", action="store_true")\n')
    evaluation.write_text(body)
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_motion_trace.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py'], cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    (SOURCE / 'CPU_public_physical_hold_r18.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
        purpose='pass requested 4mm tolerance to real servo; positive public hold requires measured motion',
        CPU_validation={'command': check.args, 'output': check.stdout})
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    for name, regression_seed in (('bottle_analytic', 9304043), ('bottle_pi05', 9301104), ('cup_pi05', 9301387)):
        old = BASE / name / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(old.read_text()))
        if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
            raise ValueError('unchanged original perturbation selection100 required')
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        old_producer = plan['producer']['path']
        plan.update(producer=pin(producer), source_path=str(SOURCE), source_commit=SOURCE.name,
            source_snapshot={**identity, 'path': str(SOURCE), 'commit': SOURCE.name,
                             'archive': {**pin(archive), 'archive_complete': True}},
            parent_plan=pin(old), qualification_authorized=False, new_training_rows=0,
            purpose='same selection pool; measure physical hold window with RGB-D and public action counters')
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if path.is_relative_to(PARENT):
                record.update(pin(SOURCE / path.relative_to(PARENT)))
            elif str(path) == old_producer:
                record.update(pin(producer))
        for case in plan['cases']:
            case['name'] = case['name'].replace('_servo_coupling_r16', '_physical_hold_r18')
        matched = [c for c in plan['cases'] if c['layout_seed'] == regression_seed]
        if len(matched) != 1:
            raise ValueError('public short-probe regression not unique')
        plan['cases'] = matched + [c for c in plan['cases'] if c not in matched]
        for condition in plan['conditions'].values():
            condition['overrides']['grasp_required_coupling_v1'] = True
            condition['overrides']['grasp_public_hold_v1'] = True
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        task_env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCH)], env=task_env, cwd='/tmp', capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        task_env['PERTURB_SKILL_CPU_ONLY'] = '0'
        result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--nice=0', '--export=ALL', str(LAUNCH)],
            env=task_env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': result.stdout.strip(), 'plan': pin(path),
            'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
            'public_rgbd_storage_dtype': 'float32', 'private_truth_rule_unchanged': True,
            'grasp_required_coupling_v1': True, 'grasp_public_hold_v1': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
