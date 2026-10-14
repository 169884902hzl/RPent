"""Compare exact robot-mesh hulls with the existing bounds on registered states."""
import argparse
import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from coordination.prepare_geometric_rotation_scale_20261010 import pin, LOCKED_V3

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r8'
OUT = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r10'
LAUNCH = ROOT / 'coordination/run_v5_registered_grasp_diagnostic_v3r9_20261010.sbatch'
STAGING = ROOT / 'coordination/mesh_hull_selection_staging_20261010'


def replace_functions(original, staged, names):
    nodes = {n.name: n for n in ast.parse(staged).body if isinstance(n, ast.FunctionDef)}
    lines = original.splitlines()
    existing = [n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in existing} != set(names):
        raise ValueError('every targeted geometry function must exist')
    for node in sorted(existing, key=lambda n: n.lineno, reverse=True):
        new = nodes[node.name]
        lines[node.lineno-1:node.end_lineno] = staged.splitlines()[new.lineno-1:new.end_lineno]
    return '\n'.join(lines)+'\n'


def snapshot(plan):
    parent = Path(plan['source_path'])
    source = ROOT / ('source_v5_geometric_mesh_hull_20261010_r1_' + parent.name.rsplit('_', 1)[-1])
    shutil.copytree(parent, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    module = 'robots/libero/v5_geometric_grasp.py'
    original = (source / module).read_text()
    body = replace_functions(original, (STAGING / 'v5_geometric_grasp.py').read_text(),
                             ('panda_geometry', 'collision_counts'))
    body = body.replace("VERSION = 'public-geometric-grasp/pad-aligned-pose-screen-4bounds-dev'",
                        "VERSION = 'public-geometric-grasp/pad-aligned-pose-screen-mesh-hulls-dev'")
    for name in ('sample_grasps', '_opposition', 'servo_grasp_pose', 'remove_measured_hand'):
        a = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef) and n.name == name)
        b = next(n for n in ast.parse(body).body if isinstance(n, ast.FunctionDef) and n.name == name)
        if ast.dump(a, include_attributes=False) != ast.dump(b, include_attributes=False):
            raise ValueError('noncollision behavior changed: '+name)
    (source / module).write_text(body)
    test = 'tests/unit_tests/robots/libero/test_v5_geometric_grasp.py'
    staged = (STAGING / 'test_v5_geometric_grasp.py').read_text()
    node = next(n for n in ast.parse(staged).body if isinstance(n, ast.FunctionDef)
        and n.name == 'test_actual_convex_mesh_excludes_empty_aabb_corner_but_keeps_collision')
    with (source / test).open('a') as stream:
        stream.write('\n\n'+'\n'.join(staged.splitlines()[node.lineno-1:node.end_lineno])+'\n')
    if pin(source / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
        raise ValueError('locked v3 changed')
    command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', test,
        'tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py']
    checked = subprocess.run(command, cwd=source, env=dict(os.environ, PYTHONPATH=str(source),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1'), capture_output=True, text=True)
    (source / 'CPU_mesh_hull.log').write_text(checked.stdout+checked.stderr)
    checked.check_returncode()
    relatives = list(dict.fromkeys([r['relative_path'] for r in plan['source_snapshot']['files']]+[module,test]))
    identity = {**plan['source_snapshot'], 'path': str(source), 'snapshot_id': source.name,
        'parent_identity': pin(parent / 'source_identity_v3r9.json'),
        'purpose': 'actual installed collision-mesh convex hull narrow phase; IK, candidate fitting, servo and locked-v3 unchanged',
        'CPU_validation': {'command': command, 'output': checked.stdout},
        'files': [{**pin(source / r), 'relative_path': r} for r in relatives]}
    identity.pop('archive', None)
    (source / 'source_identity_v3r9.json').write_text(json.dumps(identity,indent=2)+'\n')
    archive = source.with_suffix('.tar')
    with tarfile.open(archive, 'x') as stream:
        for child in source.iterdir():stream.add(child,arcname=child.name)
    identity['archive'] = {**pin(archive), 'archive_complete': True}
    return source, identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    sources = {}
    for category in ('bottle','bowl','box','cup','frypan'):
        previous = BASE / (category+'_public_pose_screen') / 'preparation/selection.json'
        plan = copy.deepcopy(json.loads(previous.read_text()))
        parent = plan['source_path']
        if parent not in sources:sources[parent] = snapshot(plan)
        source,identity = sources[parent]
        name = category+'_mesh_hull'
        prep = OUT / name / 'preparation'
        prep.mkdir(parents=True,exist_ok=False)
        producer = prep / 'producer.py';shutil.copyfile(Path(__file__),producer)
        prior = plan['producer']['path']
        helper = ROOT / 'coordination/prepare_geometric_rotation_scale_20261010.py'
        plan.update(source_path=str(source),source_snapshot=identity,source_commit=source.name,
            parent_plan=pin(previous),producer=pin(producer),purpose=identity['purpose'],
            private_truth_rule_unchanged=True)
        plan['producer_dependencies'] = [pin(producer),pin(helper),
            pin(STAGING/'v5_geometric_grasp.py'),pin(STAGING/'test_v5_geometric_grasp.py'),
            *[r for r in plan['producer_dependencies'] if r['path'] != prior]]
        plan['conditions'] = {name:next(iter(plan['conditions'].values()))}
        for case in plan['cases']:
            case['name'] = case['paired_baseline_case']+'_'+name;case['condition'] = name
        path = prep / 'selection.json';path.write_text(json.dumps(plan,indent=2)+'\n')
        env = dict(os.environ,PERTURB_SKILL_PLAN=str(path),PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
            PERTURB_SKILL_SOURCE=str(source),PERTURB_SKILL_ADAPTER=plan['adapter_path'],
            PERTURB_SKILL_OUTPUT=str(prep.parent),PERTURB_SKILL_STARTUP='1',PERTURB_SKILL_CPU_ONLY='1')
        checked = subprocess.run(['bash',str(LAUNCH)],cwd='/tmp',env=env,capture_output=True,text=True)
        (prep/'CPU_preflight.log').write_text(checked.stdout+checked.stderr);checked.check_returncode()
        if args.submit:
            env['PERTURB_SKILL_CPU_ONLY'] = '0'
            submitted = subprocess.run(['sbatch','--parsable','--chdir=/tmp','--export=ALL',str(LAUNCH)],
                env=env,capture_output=True,text=True,check=True)
            receipt = {'name':name,'startup_job':submitted.stdout.strip(),'plan':pin(path),
                'launcher':pin(LAUNCH),'CPU_preflight':checked.stdout,'qualification_allowed':False,
                'training_allowed':False,'private_truth_rule_unchanged':True}
            (prep/'submission.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps({'category':category,'startup_job':receipt['startup_job']}),flush=True)


if __name__ == '__main__':main()
