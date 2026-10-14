"""Test a supported RGB-D bottle-cap fit on the unchanged selection pool."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from coordination.prepare_bowl_pan_contact_precision_selection_20261010 import pin

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_analytic_side_route_wired_r13_20261010_r1'
SOURCE = ROOT / 'source_v5_bottle_height_envelope_r14_20261010_r1'
STAGING = ROOT / 'coordination/bottle_height_envelope_r14_staging'
OLD = ROOT / 'results/harness_v5/analytic_contact_precision_r12_selection_20261010_r2/bottle_analytic/preparation/selection.json'
OUT = ROOT / 'results/harness_v5/bottle_height_envelope_r14_selection_20261010_r1/bottle_analytic'
LAUNCHER = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    for relative in ('robots/libero/v5_analytic_grasp.py', 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py'):
        shutil.copyfile(STAGING / Path(relative).name, SOURCE / relative)
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    parameter = '        analytic_contact_precision_v1: bool = False,\n'
    assignment = '        self.analytic_contact_precision_v1 = analytic_contact_precision_v1\n'
    if body.count(parameter) != 1 or body.count(assignment) != 1:
        raise ValueError('unexpected contact feature layout')
    body = body.replace(parameter, parameter + '        analytic_height_envelope_v1: bool = False,\n')
    runtime.write_text(body.replace(assignment, assignment + '        self.analytic_height_envelope_v1 = analytic_height_envelope_v1\n'))
    evaluation = SOURCE / 'harness_v5_eval.py'
    body = evaluation.read_text()
    marker = '"analytic_contact_precision_v1",'
    if body.count(marker) != 1:
        raise ValueError('unexpected evaluator forwarding layout')
    body = body.replace(marker, marker + ' "analytic_height_envelope_v1",')
    marker = '    parser.add_argument("--grasp-measurement-calibration", type=Path)'
    if body.count(marker) != 1:
        raise ValueError('unexpected evaluator parser layout')
    evaluation.write_text(body.replace(marker, '    parser.add_argument("--analytic-height-envelope-v1", action="store_true")\n' + marker))
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'], cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    (SOURCE / 'CPU_bottle_height_envelope_r14.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
        purpose='test visible bottle-cap upper surface after palm contact stall; unchanged 2mm contact arrival and truth',
        CPU_validation={'command': check.args, 'output': check.stdout})
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    plan = copy.deepcopy(json.loads(OLD.read_text()))
    old_source, old_producer = Path(plan['source_path']), plan['producer']['path']
    if len(plan['cases']) != 100 or plan.get('confirmation') or plan.get('training_allowed'):
        raise ValueError('original unchanged selection100 required')
    prep = OUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    shutil.copyfile(Path(__file__), producer)
    plan.update(producer=pin(producer), source_path=str(SOURCE), source_commit=SOURCE.name,
        source_snapshot={**identity, 'path': str(SOURCE), 'commit': SOURCE.name,
                         'archive': {**pin(archive), 'archive_complete': True}},
        parent_plan=pin(OLD), qualification_authorized=False, new_training_rows=0,
        purpose='same selection pool; preserve locally supported bottle cap instead of clipping its sparse upper points')
    for record in plan['producer_dependencies']:
        path = Path(record['path'])
        if path.is_relative_to(old_source):
            record.update(pin(SOURCE / path.relative_to(old_source)))
        elif str(path) == old_producer:
            record.update(pin(producer))
    for case in plan['cases']:
        case['name'] += '_upper_envelope_r14'
    matched = [c for c in plan['cases'] if c['layout_seed'] == 9301141]
    if len(matched) != 1:
        raise ValueError('measured palm-stall regression not uniquely present')
    plan['cases'] = matched + [c for c in plan['cases'] if c not in matched]
    for condition in plan['conditions'].values():
        condition['overrides']['analytic_height_envelope_v1'] = True
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    environment = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    cpu = subprocess.run(['bash', str(LAUNCHER)], cwd='/tmp', env=environment, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    environment['PERTURB_SKILL_CPU_ONLY'] = '0'
    result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--nice=0', '--export=ALL', str(LAUNCHER)],
        env=environment, capture_output=True, text=True, check=True)
    receipt = {'name': 'bottle_analytic', 'startup_job': result.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCHER), 'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
        'public_rgbd_storage_dtype': 'float32', 'private_truth_rule_unchanged': True,
        'analytic_height_envelope_v1': True, 'analytic_contact_precision_v1': True}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
