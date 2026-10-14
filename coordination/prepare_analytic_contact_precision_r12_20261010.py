"""Replay selection grasps with precise contact arrival; locked truth unchanged."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_float32_r11_20261010_r2'
SOURCE = ROOT / 'source_v5_analytic_contact_precision_r12_20261010_r2'
STAGING = ROOT / 'coordination/analytic_contact_precision_r12_staging'
BASE = ROOT / 'results/harness_v5/public_grasp_float32_r11_selection_20261010_r2'
OUT = ROOT / 'results/harness_v5/analytic_contact_precision_r12_selection_20261010_r2'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('robots/libero/v5_analytic_grasp.py',
                     'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py'):
        shutil.copyfile(STAGING / relative, SOURCE / relative)
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    parameter = '        analytic_grasp_v1: bool = False,\n'
    assignment = '        self.analytic_grasp_v1 = analytic_grasp_v1\n'
    if body.count(parameter) != 1 or body.count(assignment) != 1:
        raise ValueError('unexpected analytic switch layout')
    body = body.replace(parameter, parameter + '        analytic_contact_precision_v1: bool = False,\n')
    body = body.replace(assignment, assignment + '        self.analytic_contact_precision_v1 = analytic_contact_precision_v1\n')
    runtime.write_text(body)
    evaluation = SOURCE / 'harness_v5_eval.py'
    body = evaluation.read_text()
    if body.count('"analytic_grasp_v1",') != 1:
        raise ValueError('unexpected harness feature forwarding')
    evaluation.write_text(body.replace('"analytic_grasp_v1",',
                                      '"analytic_grasp_v1", "analytic_contact_precision_v1",'))
    env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1')
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
        'tests/unit_tests/robots/libero/test_libero_observation_precision.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'],
        env=env, cwd=SOURCE, capture_output=True, text=True)
    (SOURCE / 'CPU_analytic_contact_precision_r12.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
                    purpose='require precise analytic contact pose before closing; private truth unchanged',
                    analytic_contact_source=pin(SOURCE / 'robots/libero/v5_analytic_grasp.py'),
                    CPU_validation={'command': check.args, 'output': check.stdout})
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    for name in ('bottle_analytic',):
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
                    purpose='development regression of shallow analytic contact arrival; no confirmation qualification',
                    new_evidence_replay=True, new_training_rows=0)
        for record in plan['producer_dependencies']:
            path = Path(record['path'])
            if str(path) == prior_producer:
                record.update(pin(producer))
            elif path.is_relative_to(PARENT):
                record.update(pin(SOURCE / path.relative_to(PARENT)))
        for case in plan['cases']:
            case['name'] = case['name'].replace('_public_float32_r11', '_analytic_contact_precision_r12')
        if name == 'bottle_analytic':
            regression = 'selection_grasp_bottle_9301109_analytic_analytic_contact_precision_r12'
            matches = [case for case in plan['cases'] if case['name'] == regression]
            if len(matches) != 1:
                raise ValueError('exact development regression missing')
            plan['cases'] = matches + [case for case in plan['cases'] if case['name'] != regression]
            plan['startup_regression_case'] = regression
        for condition in plan['conditions'].values():
            condition.setdefault('overrides', {})['analytic_contact_precision_v1'] = True
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
                   'public_rgbd_storage_dtype': 'float32', 'public_verdict_rule_unchanged': True,
                   'analytic_contact_precision_v1': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
