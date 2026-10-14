"""Same locked box states, with measured opposing oblique wrist views."""
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
PARENT_PLAN = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r5/box_coherent_sampling/preparation/selection.json'
SOURCE = ROOT / 'source_v5_geometric_grasp_box_oblique_20261010_r2'
OUTPUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r6/box_oblique_views_r2'
STAGING = ROOT / 'coordination/box_oblique_staging_20261010_r1'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def insert(body, old, new):
    if body.count(old) != 1:
        raise ValueError('ambiguous source insertion')
    return body.replace(old, new)


def main():
    plan = copy.deepcopy(json.loads(PARENT_PLAN.read_text()))
    parent = Path(plan['source_path'])
    shutil.copytree(parent, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    changed = ['robots/libero/v5_grasp_geometry.py', 'tests/unit_tests/robots/libero/test_v5_grasp_geometry.py']
    for relative in changed:
        shutil.copyfile(STAGING / relative, SOURCE / relative)
    analytic = SOURCE / 'robots/libero/v5_analytic_grasp.py'
    body = analytic.read_text()
    staged = (STAGING / 'robots/libero/v5_analytic_grasp.py').read_text()
    node = next(n for n in ast.parse(staged).body if isinstance(n, ast.FunctionDef)
                and n.name == 'refine_box_grasp_views')
    helper = '\n'.join(staged.splitlines()[node.lineno-1:node.end_lineno])
    line = '    plan = fit(obj)\n    receipt["analytic_grasp_plan"] = plan\n'
    body = insert(body, line, '    plan = fit(obj)\n'
        "    if (not plan['valid'] and getattr(executor, 'geometric_grasp_active_views_v1', False)\n"
        "            and obj.name in ('butter', 'cream cheese', 'chocolate pudding', 'box')):\n"
        '        obj = refine_box_grasp_views(executor, obj, receipt)\n'
        '        plan = fit(obj)\n    receipt["analytic_grasp_plan"] = plan\n')
    body += '\n\n' + helper + '\n'
    compile(body, str(analytic), 'exec')
    analytic.write_text(body)
    runtime = SOURCE / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    line = '        geometric_grasp_sampling_v1: bool = False,\n'
    body = insert(body, line, line + '        geometric_grasp_active_views_v1: bool = False,\n')
    line = '        self.geometric_grasp_sampling_v1 = geometric_grasp_sampling_v1\n'
    body = insert(body, line, line + '        self.geometric_grasp_active_views_v1 = geometric_grasp_active_views_v1\n')
    compile(body, str(runtime), 'exec')
    runtime.write_text(body)
    changed += ['robots/libero/v5_analytic_grasp.py', 'robots/libero/v5_runtime.py']
    tests = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', *[
        'tests/unit_tests/robots/libero/' + name for name in
        ('test_v5_grasp_geometry.py', 'test_v5_geometric_grasp.py',
         'test_v5_analytic_grasp.py::test_unmeasured_handle_gets_close_wrist_view_before_contact_is_rejected',
         'test_v5_analytic_grasp.py::test_precontact_tracking_uses_prior_identity_not_category_only_refresh',
         'test_v5_analytic_grasp.py::test_failed_approach_never_calls_policy_or_closes')]]
    checked = subprocess.run(tests, cwd=SOURCE, env=dict(os.environ, PYTHONPATH=str(SOURCE),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'), capture_output=True, text=True)
    (SOURCE / 'CPU_box_oblique.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    paths = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']] + changed))
    identity = {**plan['source_snapshot'], 'path': str(SOURCE), 'snapshot_id': SOURCE.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'opposing oblique RGB-D wrist views; stationary instance; visible hand-sweep collision checks',
        'CPU_validation': {'command': tests, 'output': checked.stdout},
        'files': [{**pin(SOURCE / relative), 'relative_path': relative} for relative in paths]}
    (SOURCE / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = SOURCE.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in SOURCE.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    prep = OUTPUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    shutil.copyfile(Path(__file__), producer)
    plan.update(source_path=str(SOURCE), source_snapshot=identity, source_commit=SOURCE.name,
        parent_plan=pin(PARENT_PLAN), producer=pin(producer),
        producer_dependencies=[pin(producer), *[d for d in plan['producer_dependencies']
                               if d['path'] != plan['producer']['path']]],
        purpose=identity['purpose'], private_truth_rule_unchanged=True)
    condition = next(iter(plan['conditions'].values()))
    condition['overrides']['geometric_grasp_active_views_v1'] = True
    group = OUTPUT.name
    plan['conditions'] = {group: condition}
    for case in plan['cases']:
        case['name'] = case['paired_baseline_case'] + '_' + group
        case['condition'] = group
    path = prep / 'selection.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
        PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=plan['adapter_path'],
        PERTURB_SKILL_OUTPUT=str(OUTPUT), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
    checked = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    env['PERTURB_SKILL_CPU_ONLY'] = '0'
    submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--export=ALL', str(LAUNCH)],
                               env=env, capture_output=True, text=True, check=True)
    receipt = {'name': group, 'startup_job': submitted.stdout.strip(), 'plan': pin(path),
        'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout, 'qualification_allowed': False,
        'training_allowed': False, 'private_truth_rule_unchanged': True, 'public_method': group}
    (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
