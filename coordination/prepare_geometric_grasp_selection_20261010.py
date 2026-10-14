"""Pair public geometry repairs and geometric sampling on locked r14 states."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/servo_only_fiveclass_selection_20261010_r1'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r1'
STAGING = ROOT / 'coordination/geometric_grasp_staging_20261010_r1'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261010_v3r9'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
XML = ROOT / '.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def insert(body, old, new):
    if body.count(old) != 1:
        raise ValueError('source insertion not unique: ' + old)
    return body.replace(old, new)


def snapshot(parent, parent_identity):
    source = ROOT / ('source_v5_geometric_grasp_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    added = ('robots/libero/v5_analytic_grasp.py', 'robots/libero/v5_grasp_geometry.py',
             'robots/libero/v5_geometric_grasp.py', 'robots/libero/v5_grasp_public_tracking.py',
             'tests/unit_tests/robots/libero/test_v5_grasp_geometry.py',
             'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py')
    for relative in added:
        shutil.copyfile(STAGING / relative, source / relative)
    runtime = source / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    line = '        analytic_grasp_v1: bool = False,\n'
    body = insert(body, line, line + '        analytic_identity_guard_v1: bool = False,\n'
        '        analytic_geometry_v1: bool = False,\n        geometric_grasp_sampling_v1: bool = False,\n'
        '        geometric_gripper_xml: str | None = None,\n')
    line = '        self.analytic_grasp_v1 = analytic_grasp_v1\n'
    body = insert(body, line, line + '        self.analytic_identity_guard_v1 = analytic_identity_guard_v1\n'
        '        self.analytic_geometry_v1 = analytic_geometry_v1\n'
        '        self.geometric_grasp_sampling_v1 = geometric_grasp_sampling_v1\n'
        '        self.geometric_gripper_xml = geometric_gripper_xml\n')
    line = '                 record_sam_masks_v6: bool = False,\n'
    body = insert(body, line, line + '                 grasp_geometry_cleanup_v1: bool = False,\n')
    line = '        self.record_sam_masks_v6 = record_sam_masks_v6\n'
    body = insert(body, line, line + '        self.grasp_geometry_cleanup_v1 = grasp_geometry_cleanup_v1\n')
    primary = '                    raise ValueError("SAM/depth image dimensions differ")\n'
    body = insert(body, primary, primary +
        '                if self.grasp_geometry_cleanup_v1 and name in ("butter", "cream cheese", "chocolate pudding", "box"):\n'
        '                    from robots.libero.v5_grasp_geometry import clean_object_mask\n'
        '                    mask, _ = clean_object_mask(world, mask)\n')
    secondary = '                        raise ValueError("secondary SAM/depth dimensions differ")\n'
    body = insert(body, secondary, secondary +
        '                    if self.grasp_geometry_cleanup_v1 and name in ("butter", "cream cheese", "chocolate pudding", "box"):\n'
        '                        from robots.libero.v5_grasp_geometry import clean_object_mask\n'
        '                        mask, _ = clean_object_mask(secondary_world, mask)\n')
    runtime.write_text(body)
    tests = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_grasp_geometry.py',
        'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py'], cwd=source,
        env=dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
    (source / 'CPU_geometric_grasp.log').write_text(tests.stdout + tests.stderr)
    tests.check_returncode()
    paths = list(dict.fromkeys([r['relative_path'] for r in parent_identity['files']]
                              + list(added) + ['robots/libero/v5_runtime.py']))
    identity = {**parent_identity, 'path': str(source), 'snapshot_id': source.name, 'commit': source.name,
        'parent_snapshot': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'public geometry method selection; robot STL bounds, no weights or private scene poses',
        'CPU_validation': {'command': tests.args, 'output': tests.stdout},
        'files': [{**pin(source / p), 'relative_path': p} for p in paths]}
    (source / 'source_identity_v3r9.json').write_text(json.dumps(identity, indent=2) + '\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():
            stream.add(child, arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    return source, identity


def main():
    sources = {}
    cells = [('box', 'depth_cleanup'), ('cup', 'identity_guard'), ('frypan', 'connected_handle')]
    cells += [(category, 'geometric_sampling') for category in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
    for category, method in cells:
        old = BASE / (category + '_analytic') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(old.read_text()))
        parent = Path(plan['source_path'])
        if parent not in sources:
            sources[parent] = snapshot(parent, plan['source_snapshot'])
        source, identity = sources[parent]
        prep = OUT / (category + '_' + method) / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        shutil.copyfile(Path(__file__), producer)
        prior_producer = plan['producer']['path']
        plan.update(source_path=str(source), source_snapshot=identity, source_commit=source.name,
            parent_plan=pin(old), producer=pin(producer), new_training_rows=0,
            purpose='same r14 selection states; ' + method + '; private v3 scorer unchanged')
        plan['producer_dependencies'] = [pin(producer), *[
            r for r in plan['producer_dependencies'] if r['path'] != prior_producer]]
        condition = next(iter(plan['conditions'].values()))
        overrides = condition['overrides']
        overrides.update(record_sam_masks_v6=True, analytic_grasp_v1=True)
        if method in ('identity_guard', 'geometric_sampling'):
            overrides['analytic_identity_guard_v1'] = True
        if method in ('connected_handle', 'geometric_sampling'):
            overrides['analytic_geometry_v1'] = True
        if method in ('depth_cleanup', 'geometric_sampling'):
            overrides['grasp_geometry_cleanup_v1'] = True
        if method == 'geometric_sampling':
            overrides.update(geometric_grasp_sampling_v1=True, geometric_gripper_xml=str(XML))
        plan['conditions'] = {method: condition}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case'] + '_' + method
            case['condition'] = method
        # Exercise the known failures at physical startup, never score-select states.
        seed = {'box': 9301225, 'cup': 9306044, 'frypan': 9301400}.get(category)
        matches = [c for c in plan['cases'] if c['layout_seed'] == seed]
        if matches:
            plan['cases'] = matches + [c for c in plan['cases'] if c not in matches]
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(os.environ, PERTURB_SKILL_PLAN=str(path), PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source), PERTURB_SKILL_ADAPTER=str(ADAPTER),
            PERTURB_SKILL_OUTPUT=str(prep.parent), PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1')
        cpu = subprocess.run(['bash', str(LAUNCH)], cwd='/tmp', env=env, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        env['PERTURB_SKILL_CPU_ONLY'] = '0'
        submitted = subprocess.run(['sbatch', '--parsable', '--chdir=/tmp', '--nice=0',
            '--export=ALL', str(LAUNCH)], env=env, capture_output=True, text=True, check=True)
        receipt = {'name': prep.parent.name, 'startup_job': submitted.stdout.strip(),
            'plan': pin(path), 'launcher': pin(LAUNCH), 'CPU_preflight': cpu.stdout,
            'qualification_allowed': False, 'private_truth_rule_unchanged': True,
            'public_method': method, 'paired_baseline': pin(old)}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
