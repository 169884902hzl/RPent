"""Test the existing public co-motion verifier with connected-handle execution."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT_PLAN = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r3/frypan_connected_handle/preparation/selection.json'
VERIFIER = ROOT / 'source_v5_public_physical_hold_r18_20261010_r1'
SOURCE = ROOT / 'source_v5_pan_public_coupling_20261010_r1'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r13/frypan_public_coupling'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise ValueError('nonunique source patch: ' + old)
    return body.replace(old, new)


def methods(body):
    return {node.name: node for owner in ast.parse(body).body
            if isinstance(owner, ast.ClassDef) and owner.name == 'V5Executor'
            for node in owner.body if isinstance(node, ast.FunctionDef)}


def main():
    plan = copy.deepcopy(json.loads(PARENT_PLAN.read_text()))
    parent = Path(plan['source_path'])
    shutil.copytree(parent, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    donor = (VERIFIER / 'robots/libero/v5_runtime.py').read_text()
    existing, replacements = methods(body), methods(donor)
    lines = body.splitlines(keepends=True)
    selected = ('independent_grasp_frame', 'verify_independent_grasp')
    for name in sorted(selected, key=lambda name: existing[name].lineno, reverse=True):
        node, new = existing[name], replacements[name]
        lines[node.lineno-1:node.end_lineno] = donor.splitlines(keepends=True)[new.lineno-1:new.end_lineno]
    body = ''.join(lines)
    extra = ''.join('\n' + ''.join(donor.splitlines(keepends=True)[replacements[name].lineno-1:replacements[name].end_lineno])
                    for name in ('measure_public_grasp_hold', '_measure_grasp_pad_regions'))
    body = replace_once(body, '    def verify_grasp_measurement(', extra + '\n    def verify_grasp_measurement(')
    body = replace_once(body, '        grasp_independent_views_v1: bool = False,\n',
        '        grasp_independent_views_v1: bool = False,\n'
        '        grasp_public_tracking_v1: bool = False,\n'
        '        grasp_required_coupling_v1: bool = False,\n'
        '        grasp_public_hold_v1: bool = False,\n')
    body = replace_once(body, '        self.grasp_independent_views_v1 = grasp_independent_views_v1\n',
        '        self.grasp_independent_views_v1 = grasp_independent_views_v1\n'
        '        self.grasp_public_tracking_v1 = grasp_public_tracking_v1\n'
        '        self.grasp_required_coupling_v1 = grasp_required_coupling_v1\n'
        '        self.grasp_public_hold_v1 = grasp_public_hold_v1\n'
        '        self.grasp_public_closing_xyz = None\n')
    compile(body, str(runtime), 'exec')
    runtime.write_text(body)
    added = ('robots/libero/v5_grasp_public_tracking.py',
             'robots/libero/v5_grasp_measurement.py',
             'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py',
             'tests/unit_tests/robots/libero/test_v5_grasp_measurement.py')
    for relative in added:
        shutil.copyfile(VERIFIER / relative, SOURCE / relative)
    checked = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        *added[2:]], cwd=SOURCE,
        env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE='1',
                 OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'), capture_output=True, text=True)
    (SOURCE / 'CPU_public_coupling.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    actual_v3 = pin(SOURCE / 'robots/libero/v5_grasp_truth.py')['sha256']
    # Keep the registered v3 identity exact, including the full SHA length.
    if actual_v3 != LOCKED_V3:
        raise ValueError('locked v3 changed')
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']] + list(added)))
    identity = {**plan['source_snapshot'], 'path': str(SOURCE), 'snapshot_id': SOURCE.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'verifier_donor_identity': pin(VERIFIER / 'source_identity_v3r9.json'),
        'purpose': 'connected-handle motion unchanged; existing RGB-D active lift and physical hold verifier',
        'CPU_validation': {'command': checked.args, 'output': checked.stdout},
        'files': [{**pin(SOURCE / relative), 'relative_path': relative} for relative in relatives]}
    identity.pop('archive', None)
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in SOURCE.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    prep = OUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    shutil.copyfile(Path(__file__), producer)
    prior = plan['producer']['path']
    plan.update(source_path=str(SOURCE), source_snapshot=identity, source_commit=SOURCE.name,
        parent_plan=pin(PARENT_PLAN), producer=pin(producer), purpose=identity['purpose'])
    plan['producer_dependencies'] = [pin(producer), *[r for r in plan['producer_dependencies'] if r['path'] != prior]]
    condition = next(iter(plan['conditions'].values()))
    condition['overrides'].update(grasp_public_tracking_v1=True,
        grasp_required_coupling_v1=True, grasp_public_hold_v1=True)
    plan['conditions'] = {OUT.name: condition}
    for case in plan['cases']:
        case.update(name=case['paired_baseline_case'] + '_' + OUT.name, condition=OUT.name)
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    cpu = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    result = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
        env=env, capture_output=True, text=True, check=True)
    receipt = {'name': OUT.name, 'startup_job': result.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout, 'qualification_allowed': False,
        'training_allowed': False, 'private_truth_rule_unchanged': True,
        'diagnosis': pin(ROOT / 'coordination/pan_connected_handle_public_false_negatives_20261010_r1/manifest.json')}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
