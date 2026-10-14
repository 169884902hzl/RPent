"""Pair public joint-limit pose screening with the unchanged pad-aligned method."""
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
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r8'
STAGING = ROOT / 'coordination/pose_screen_staging_20261010'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def insert(body, old, new):
    if body.count(old) != 1:
        raise ValueError('ambiguous source insertion')
    return body.replace(old, new)


def snapshot(plan):
    parent = Path(plan['source_path'])
    source = ROOT / ('source_v5_geometric_pose_screen_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    relative = 'robots/libero/v5_geometric_grasp.py'
    original, staged = (source / relative).read_text(), (STAGING / relative).read_text()
    node = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == 'sample_grasps')
    replacement = next(n for n in ast.parse(staged).body if isinstance(n, ast.FunctionDef) and n.name == 'sample_grasps')
    lines = original.splitlines()
    lines[node.lineno-1:node.end_lineno] = staged.splitlines()[replacement.lineno-1:replacement.end_lineno]
    body = '\n'.join(lines) + '\n'
    body, n = re.subn(r'^VERSION = .+$', "VERSION = 'public-geometric-grasp/pad-aligned-pose-screen-4bounds-dev'", body, flags=re.M)
    if n != 1:
        raise ValueError('one module version required')
    for name in ('_opposition', 'panda_geometry', 'collision_counts', 'remove_measured_hand'):
        a = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in ast.parse(body).body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(a, include_attributes=False) != ast.dump(b, include_attributes=False):
            raise ValueError('contact geometry or collision rules changed in the pose screen comparison')
    (source / relative).write_text(body)
    analytic = source / 'robots/libero/v5_analytic_grasp.py'
    body = analytic.read_text()
    line = "            fitted, candidates = sample_grasps(points, visible_scene, entity.name,\n"
    body = insert(body, line,
        "            pose_screen = None\n"
        "            if getattr(executor, 'geometric_pose_screen_v1', False):\n"
        "                from pathlib import Path\n"
        "                from robots.libero.v5_grasp_kinematics import PublicPoseScreen\n"
        "                robot_xml = Path(executor.geometric_gripper_xml).parent.parent / 'robots/panda/robot.xml'\n"
        "                pose_screen = PublicPoseScreen(robot_xml, observation['robot0_joint_pos'],\n"
        "                    executor.p._last_obs_eef_pos, observation['robot0_eef_quat'],\n"
        "                    geometry['site_offset_in_gripper_m'])\n" + line)
    line = "                current_body_quat_xyzw=observation['robot0_eef_quat'])\n"
    body = insert(body, line,
        "                current_body_quat_xyzw=observation['robot0_eef_quat'],\n"
        "                **({'pose_screen': pose_screen, 'approach_height': height} if pose_screen is not None else {}))\n")
    analytic.write_text(body)
    runtime = source / 'robots/libero/v5_runtime.py'
    body = runtime.read_text()
    line = '        geometric_grasp_sampling_v1: bool = False,\n'
    body = insert(body, line, line + '        geometric_pose_screen_v1: bool = False,\n')
    line = '        self.geometric_grasp_sampling_v1 = geometric_grasp_sampling_v1\n'
    body = insert(body, line, line + '        self.geometric_pose_screen_v1 = geometric_pose_screen_v1\n')
    runtime.write_text(body)
    changed = ['robots/libero/v5_geometric_grasp.py', 'robots/libero/v5_analytic_grasp.py',
        'robots/libero/v5_runtime.py', 'robots/libero/v5_grasp_kinematics.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py']
    for relative in changed[-2:]:
        shutil.copyfile(STAGING / relative, source / relative)
    for relative in changed:
        compile((source / relative).read_text(), str(source / relative), 'exec')
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q',
        'tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py',
        'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py']
    checked = subprocess.run(command, cwd=source,
        env=dict(os.environ, PYTHONPATH=str(source), OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'),
        capture_output=True, text=True)
    (source / 'CPU_pose_screen.log').write_text(checked.stdout + checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']] + changed))
    identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'public Panda joint-limit IK screens exact approach, contact and lift poses; pad fit, collision bounds and servo unchanged',
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
        previous = BASE / (category + '_pad_contact_alignment') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(previous.read_text()))
        parent = plan['source_path']
        if parent not in sources:
            sources[parent] = snapshot(plan)
        source, identity = sources[parent]
        name = category + '_public_pose_screen'
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
        condition['overrides']['geometric_pose_screen_v1'] = True
        plan['conditions'] = {name: condition}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case'] + '_' + name
            case['condition'] = name
        path = prep / 'selection.json'
        path.write_text(json.dumps(plan, indent=2) + '\n')
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
            'launcher': pin(LAUNCH), 'CPU_preflight': checked.stdout,
            'qualification_allowed': False, 'training_allowed': False, 'private_truth_rule_unchanged': True}
        (prep / 'submission.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'category': category, 'startup_job': receipt['startup_job'], 'source': str(source)}), flush=True)


if __name__ == '__main__':
    main()
