"""Wire the existing precision contact code into immutable sampler snapshots."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r5'
OUTPUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
STAGED_TEST = ROOT / 'coordination/contact_precision_staging_20261010/test_v5_analytic_grasp.py'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def insert(body, old, new):
    if body.count(old) != 1:
        raise ValueError('ambiguous source insertion')
    return body.replace(old, new)


def snapshot(plan):
    parent = Path(plan['source_path'])
    source = ROOT / ('source_v5_geometric_precision_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    runtime = source / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    if '        analytic_contact_precision_v1: bool = False,\n' in body:
        raise ValueError('parent already exposes precision; do not silently duplicate an experiment')
    line = '        analytic_geometry_v1: bool = False,\n'
    body = insert(body, line, line + '        analytic_contact_precision_v1: bool = False,\n')
    line = '        self.analytic_geometry_v1 = analytic_geometry_v1\n'
    body = insert(body, line, line + '        self.analytic_contact_precision_v1 = analytic_contact_precision_v1\n')
    compile(body, str(runtime), 'exec')
    runtime.write_text(body)
    analytic = source / 'robots/libero/v5_analytic_grasp.py'
    if "tolerance = .002 if precise_contact else .008" not in analytic.read_text():
        raise ValueError('this experiment only wires the existing contact code; it cannot alter it')
    test = source / 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py'
    shutil.copyfile(STAGED_TEST, test)
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py::test_shallow_contact_missed_by_five_mm_is_not_closed_in_precision_mode',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py::test_failed_approach_never_calls_policy_or_closes',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py::test_precontact_tracking_uses_prior_identity_not_category_only_refresh']
    env = dict(os.environ, PYTHONPATH=str(source), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    checked = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True)
    (source / 'CPU_contact_precision.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    # Exercise the actual class interface used by the runner; the previous
    # sampler had contact code but its constructor silently omitted this flag.
    command2 = [str(ROOT / '.venv/bin/python'), '-c',
        "from types import SimpleNamespace; from robots.libero.v5_runtime import V5Executor; "
        "e=V5Executor(SimpleNamespace(primitives=SimpleNamespace()),SimpleNamespace(),"
        "analytic_contact_precision_v1=True); assert e.analytic_contact_precision_v1 is True"]
    wired = subprocess.run(command2, cwd=source, env=env, capture_output=True, text=True)
    (source / 'CPU_contact_precision_interface.log').write_text(wired.stdout + wired.stderr)
    wired.check_returncode()
    changed = ['robots/libero/v5_runtime.py', 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py']
    paths = list(dict.fromkeys([f['relative_path'] for f in plan['source_snapshot']['files']] + changed))
    identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': '2mm analytic contact precision; contact policy, meshes and locked-v3 labels unchanged',
        'CPU_validation': {'command': command, 'output': checked.stdout,
                           'interface_command': command2, 'interface_exit_code': wired.returncode},
        'files': [{**pin(source / relative), 'relative_path': relative} for relative in paths]}
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
        name = category + '_coherent_precision'
        prep = OUTPUT / name / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        previous_producer = plan['producer']['path']
        plan.update(source_path=str(source), source_snapshot=identity, source_commit=source.name,
            parent_plan=pin(previous), producer=pin(producer), purpose=identity['purpose'],
            private_truth_rule_unchanged=True)
        plan['producer_dependencies'] = [pin(producer), *[
            p for p in plan['producer_dependencies'] if p['path'] != previous_producer]]
        condition = next(iter(plan['conditions'].values()))
        condition['overrides']['analytic_contact_precision_v1'] = True
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
            'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout, 'qualification_allowed': False,
            'training_allowed': False, 'private_truth_rule_unchanged': True, 'public_method': name}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
