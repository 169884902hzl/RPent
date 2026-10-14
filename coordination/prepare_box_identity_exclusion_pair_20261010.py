"""Pair current-mask package identity filtering on the unchanged box selection pool."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT_PLAN = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r4/box_depth_identity_cleanup/preparation/selection.json'
SOURCE = ROOT / 'source_v5_box_identity_exclusion_20261010_r1'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r11/box_identity_exclusion'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
STAGING = ROOT / 'coordination/box_identity_exclusion_staging_20261010'
LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    plan = copy.deepcopy(json.loads(PARENT_PLAN.read_text()))
    parent = Path(plan['source_path'])
    shutil.copytree(parent, SOURCE, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    relative = 'robots/libero/v5_runtime.py'
    path = SOURCE / relative
    body = path.read_text()
    anchor = '            limit = self.instance_limits.get(name)\n'
    if body.count(anchor) != 1:
        raise ValueError('expected one category-limit boundary')
    patch = (STAGING / 'current_package_mask_filter.txt').read_text()
    body = body.replace(anchor, patch + anchor)
    compile(body, str(path), 'exec')
    path.write_text(body)
    test_relative = 'tests/unit_tests/robots/libero/test_v5_package_identity_conflict.py'
    shutil.copyfile(STAGING / 'test_v5_package_identity_conflict.py', SOURCE / test_relative)
    if pin(SOURCE / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
        raise ValueError('locked v3 must remain unchanged')
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', test_relative,
               'tests/unit_tests/robots/libero/test_v5_runtime.py', '-k', 'package or distinct_stacked_masks']
    checked = subprocess.run(command, cwd=SOURCE, env=dict(os.environ,
        PYTHONPATH=str(SOURCE), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
        capture_output=True, text=True)
    (SOURCE / 'CPU_identity_exclusion.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']]
                                   + [relative, test_relative]))
    identity = {**plan['source_snapshot'], 'path': str(SOURCE), 'snapshot_id': SOURCE.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'filter another current package mask before old-ID association and instance limit; execution, budgets and locked-v3 unchanged',
        'CPU_validation': {'command': command, 'output': checked.stdout},
        'files': [{**pin(SOURCE / r), 'relative_path': r} for r in relatives]}
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
    plan['producer_dependencies'] = [pin(producer), pin(STAGING / 'current_package_mask_filter.txt'),
        pin(STAGING / 'test_v5_package_identity_conflict.py'),
        *[r for r in plan['producer_dependencies'] if r['path'] != prior]]
    name = OUT.name
    plan['conditions'] = {name: next(iter(plan['conditions'].values()))}
    for case in plan['cases']:
        case.update(name=case['paired_baseline_case'] + '_' + name, condition=name)
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
        PERTURB_SKILL_OUTPUT=str(OUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                               env=env, capture_output=True, text=True, check=True)
    receipt = {'name': name, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout, 'qualification_allowed': False,
        'training_allowed': False, 'private_truth_rule_unchanged': True}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'startup_job': receipt['startup_job'], 'source': str(SOURCE)}), flush=True)


if __name__ == '__main__':
    main()
