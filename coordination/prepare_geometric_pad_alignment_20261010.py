"""Pair measured pad-centre contact poses with the unchanged coherent sampler."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r5'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
STAGING = ROOT / 'coordination/pad_contact_alignment_staging_20261010'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def replace_functions(original, replacement, names):
    nodes = {n.name: n for n in ast.parse(replacement).body if isinstance(n, ast.FunctionDef)}
    lines = original.splitlines()
    selected = [n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in selected} != set(names):
        raise ValueError('every targeted function must exist exactly once')
    for node in sorted(selected, key=lambda n: n.lineno, reverse=True):
        new = nodes[node.name]
        lines[node.lineno-1:node.end_lineno] = replacement.splitlines()[new.lineno-1:new.end_lineno]
    return '\n'.join(lines) + '\n'


def snapshot(plan):
    parent = Path(plan['source_path'])
    source = ROOT / ('source_v5_geometric_pad_alignment_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    path = source / 'robots/libero/v5_geometric_grasp.py'
    body = replace_functions(path.read_text(), (STAGING / 'v5_geometric_grasp.py').read_text(),
                             ('_opposition', 'sample_grasps'))
    body, n = re.subn(r'^VERSION = .+$', "VERSION = 'public-geometric-grasp/pad-aligned-4bounds-dev'", body, flags=re.M)
    if n != 1:
        raise ValueError('one module version required')
    compile(body, str(path), 'exec')
    path.write_text(body)
    # Preserve the old 4-dev robot bounds and collision implementation.
    before = ast.parse((parent / 'robots/libero/v5_geometric_grasp.py').read_text())
    after = ast.parse(body)
    for name in ('panda_geometry', 'collision_counts', 'remove_measured_hand'):
        a = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(a, include_attributes=False) != ast.dump(b, include_attributes=False):
            raise ValueError('mesh model changed during the contact-point comparison')
    test = source / 'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py'
    staged = (STAGING / 'test_v5_geometric_grasp.py').read_text()
    tests = replace_functions(test.read_text(), staged, ('gripper_geometry',))
    for node in ast.parse(staged).body:
        if isinstance(node, ast.FunctionDef) and node.name in (
                'test_contact_centre_uses_measured_flanks_instead_of_high_search_band_origin',
                'test_top_and_side_tcp_offsets_match_robot_pad_centre'):
            tests += '\n\n' + '\n'.join(staged.splitlines()[node.lineno-1:node.end_lineno]) + '\n'
    test.write_text(tests)
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
               'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']
    checked = subprocess.run(command, cwd=source,
        env=dict(os.environ, PYTHONPATH=str(source), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
        capture_output=True, text=True)
    (source / 'CPU_pad_alignment.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']]
        + ['robots/libero/v5_geometric_grasp.py', 'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']))
    identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'measured opposing patch centre plus actual robot pad-to-TCP offset; collision and servo rules unchanged',
        'CPU_validation': {'command': command, 'output': checked.stdout},
        'files': [{**pin(source / relative), 'relative_path': relative} for relative in relatives]}
    (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    return source, identity


def main():
    sources = {}
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        previous = BASE / (category + '_coherent_sampling') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(previous.read_text()))
        parent = plan['source_path']
        if parent not in sources:
            sources[parent] = snapshot(plan)
        source, identity = sources[parent]
        name = category + '_pad_contact_alignment'
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        prior_producer = plan['producer']['path']
        plan.update(source_path=str(source), source_snapshot=identity, source_commit=source.name,
            parent_plan=pin(previous), producer=pin(producer), purpose=identity['purpose'])
        plan['producer_dependencies'] = [pin(producer), *[r for r in plan['producer_dependencies']
                                                        if r['path'] != prior_producer]]
        condition = next(iter(plan['conditions'].values()))
        plan['conditions'] = {name: condition}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case'] + '_' + name
            case['condition'] = name
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env,
                                 capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
        checked.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                                   env=env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
            'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout,
            'qualification_allowed': False, 'training_allowed': False, 'private_truth_rule_unchanged': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'category': category, 'startup_job': receipt['startup_job'], 'source': str(source)}), flush=True)


if __name__ == '__main__':
    main()
