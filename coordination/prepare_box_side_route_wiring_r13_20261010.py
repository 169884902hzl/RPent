"""Wire the measured side route omitted from the historical runtime snapshot."""

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
PARENT = ROOT / 'source_v5_analytic_contact_precision_r12_20261010_r2'
SOURCE = ROOT / 'source_v5_analytic_side_route_wired_r13_20261010_r1'
STAGING = ROOT / 'coordination/box_side_route_wiring_r13_staging'
PLAN = ROOT / 'results/harness_v5/registered_grasp_v3r9_selection_20261010/box_analytic_side/preparation/selection.json'
OUT = ROOT / 'results/harness_v5/analytic_side_route_wired_box_selection_20261010_r1/box_analytic_side'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCHER = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def main():
    shutil.copytree(PARENT, SOURCE, symlinks=True,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    parameter = '        analytic_contact_precision_v1: bool = False,\n'
    assignment = '        self.analytic_contact_precision_v1 = analytic_contact_precision_v1\n'
    if body.count(parameter) != 1 or body.count(assignment) != 1 or 'self.analytic_side_route_v1 =' in body:
        raise ValueError('unexpected constructor layout; do not silently duplicate flags')
    body = body.replace(parameter, parameter + '        analytic_side_route_v1: bool = False,\n')
    body = body.replace(assignment, assignment + '        self.analytic_side_route_v1 = analytic_side_route_v1\n')
    runtime.write_text(body)
    evaluation = SOURCE / 'harness_v5_eval.py'
    body = evaluation.read_text()
    if body.count('"analytic_contact_precision_v1",') != 1 or '"analytic_side_route_v1",' in body:
        raise ValueError('unexpected evaluator feature forwarding')
    evaluation.write_text(body.replace('"analytic_contact_precision_v1",',
        '"analytic_contact_precision_v1", "analytic_side_route_v1",'))
    shutil.copyfile(STAGING / 'test_v5_analytic_grasp.py',
        SOURCE / 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py')
    check = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py'], cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1'),
        capture_output=True, text=True)
    (SOURCE / 'CPU_side_route_wiring_r13.log').write_text(check.stdout + check.stderr)
    check.check_returncode()
    identity = json.loads((PARENT / 'source_identity_v3r9.json').read_text())
    identity.update(snapshot_id=SOURCE.name, parent_snapshot=str(PARENT),
        purpose='enable the existing measured furniture side-entry route via evaluator and runtime constructor',
        CPU_validation={'command': check.args, 'output': check.stdout})
    for record in identity['files']:
        record.update(pin(SOURCE / record['relative_path']))
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'w') as stream:
        for child in SOURCE.iterdir():
            if child.name not in ('__pycache__', '.pytest_cache'):
                stream.add(child, arcname=child.name)
    plan = copy.deepcopy(json.loads(PLAN.read_text()))
    if plan.get('confirmation') or plan.get('training_allowed') or len(plan['cases']) != 100:
        raise ValueError('unchanged original perturbation selection100 required')
    prep = OUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    shutil.copyfile(Path(__file__), producer)
    prior_producer, prior_source = plan['producer']['path'], Path(plan['source_path'])
    plan.update(producer=pin(producer), source_path=str(SOURCE), source_commit=SOURCE.name,
        source_snapshot={**identity, 'path': str(SOURCE), 'commit': SOURCE.name,
            'archive': {**pin(archive), 'archive_complete': True}}, adapter_path=str(ADAPTER),
        parent_plan=pin(PLAN), qualification_authorized=False,
        purpose='actual measured side-entry configuration; historical miswired side method retained',
        new_evidence_replay=True, new_training_rows=0)
    for record in plan['producer_dependencies']:
        path = Path(record['path'])
        if str(path) == prior_producer:
            record.update(pin(producer))
        elif path.is_relative_to(prior_source):
            record.update(pin(SOURCE / path.relative_to(prior_source)))
    for case in plan['cases']:
        if pin(Path(case['registered_layout_state']['path'])) != case['registered_layout_state']:
            raise ValueError('selection layout changed')
        case['name'] += '_side_route_wired_r13'
    # Reproduce a historical descent miss; this remains a development state.
    regression = [c for c in plan['cases'] if c['layout_seed'] == 9301225]
    if len(regression) != 1:
        raise ValueError('registered public descent regression not uniquely present')
    plan['cases'] = regression + [c for c in plan['cases'] if c not in regression]
    for condition in plan['conditions'].values():
        condition.setdefault('overrides', {}).update(analytic_grasp_v1=True,
            analytic_side_route_v1=True, analytic_contact_precision_v1=True, motion_trace_v1=True,
            grasp_public_tracking_v1=True, grasp_independent_views_v1=True,
            grasp_public_coupled_lift_v1=True)
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    cpu = subprocess.run(['bash', str(LAUNCHER)], cwd='/tmp', env=env, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCHER)],
        env=env, capture_output=True, text=True, check=True)
    receipt = {'name': 'box_analytic_side', 'startup_job': result.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCHER), 'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
        'public_rgbd_storage_dtype': 'float32', 'public_verdict_rule_unchanged': True,
        'analytic_side_route_v1': True, 'analytic_contact_precision_v1': True}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
