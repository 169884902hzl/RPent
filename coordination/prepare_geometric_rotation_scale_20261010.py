"""Isolate scripted OSC rotation conversion on the same registered public states."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
TEST = ROOT / 'coordination/test_v5_rotation_action_scale_20261010.py'
LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def replace_once(body, before, after):
    if body.count(before) != 1:
        raise ValueError('expected one unchanged rotation conversion')
    return body.replace(before, after)


def snapshot(plan, development_git_commit):
    parent = Path(plan['source_path'])
    source = ROOT / ('source_v5_geometric_rotation_scale_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    changes = {
        'robots/libero/tools.py': ('rotation_action_scale: float = 0.10,',
                                  'rotation_action_scale: float = 0.50,'),
        'robots/libero/v5_geometric_grasp.py': (
            'error * min(1., .08 / max(angle, 1e-12)) / .10',
            'error * min(1., .08 / max(angle, 1e-12)) / .50'),
        'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py': (
            'Rotation.from_rotvec(action[3:6] * .10)',
            'Rotation.from_rotvec(action[3:6] * .50)'),
    }
    for relative, (before, after) in changes.items():
        path = source / relative
        body = replace_once(path.read_text(), before, after)
        compile(body, str(path), 'exec')
        path.write_text(body)
    relative_test = 'tests/unit_tests/robots/libero/test_v5_rotation_action_scale.py'
    shutil.copyfile(TEST, source / relative_test)
    if pin(source / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
        raise ValueError('locked v3 must remain unchanged')
    controller = ROOT / '.venv/lib/python3.10/site-packages/robosuite/controllers/config/robots/default_panda.json'
    values = json.loads(controller.read_text())['body_parts']['arms']['right']['output_max']
    if values != [.05, .05, .05, .5, .5, .5]:
        raise ValueError('registered controller action scale differs')
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', relative_test,
        'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']
    checked = subprocess.run(command, cwd=source, env=dict(os.environ,
        PYTHONPATH=str(source), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
        capture_output=True, text=True)
    (source / 'CPU_rotation_scale.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']]
                                  + list(changes) + [relative_test]))
    identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'development_checkout_commit': development_git_commit,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'OSC pose conversion .10 to installed .50 rotation scale only; geometry, servo tolerances, contact and locked-v3 unchanged',
        'controller_configuration': pin(controller), 'controller_output_max': values,
        'CPU_validation': {'command': command, 'output': checked.stdout},
        'files': [{**pin(source / r), 'relative_path': r} for r in relatives]}
    identity.pop('archive', None)
    (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2)+'\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    return source, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--development-git-commit', required=True)
    args = parser.parse_args()
    if len(args.development_git_commit) != 40 or any(c not in '0123456789abcdef' for c in args.development_git_commit):
        raise ValueError('an exact development checkout commit is required')
    sources = {}
    for category in ('bottle', 'bowl', 'box', 'cup', 'frypan'):
        previous = BASE / (category + '_pad_contact_alignment') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(previous.read_text()))
        parent = plan['source_path']
        if parent not in sources:
            sources[parent] = snapshot(plan, args.development_git_commit)
        source, identity = sources[parent]
        name = category + '_rotation_scale'
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        prior = plan['producer']['path']
        plan.update(source_path=str(source), source_snapshot=identity, source_commit=source.name,
            parent_plan=pin(previous), producer=pin(producer), purpose=identity['purpose'],
            private_truth_rule_unchanged=True)
        plan['producer_dependencies'] = [pin(producer), *[r for r in plan['producer_dependencies'] if r['path'] != prior]]
        plan['references'].append(identity['controller_configuration'])
        plan['conditions'] = {name: next(iter(plan['conditions'].values()))}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case'] + '_' + name
            case['condition'] = name
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2)+'\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
        checked.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
            env=env, capture_output=True, text=True, check=True)
        receipt = {'name': name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
            'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout, 'qualification_allowed': False,
            'training_allowed': False, 'private_truth_rule_unchanged': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps({'category': category, 'startup_job': receipt['startup_job'], 'source': str(source)}), flush=True)


if __name__ == '__main__':
    main()
