"""Test public measured side staging on the three retained descent failures."""

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
PARENT = ROOT / 'source_v5_analytic_pose_trace_20261009_r1'
PRIOR = ROOT / 'results/harness_v5/analytic_pose_trace3_20261009_r1/grasp_box_analytic_pose_trace/preparation/selection.json'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    source = ROOT / f'source_v5_analytic_side_route_20261009_r{args.revision}'
    output = ROOT / f'results/harness_v5/analytic_side_route3_20261009_r{args.revision}/grasp_box_analytic_side_route'
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent changed')
    shutil.copytree(PARENT, source, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['robots/libero/v5_analytic_grasp.py', 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py']
    for name in changed:
        shutil.copy2(ROOT / name, source / name)
    for name in ('robots/libero/v5_runtime.py', 'harness_v5_eval.py'):
        path = source / name
        original = path.read_text()
        if name.endswith('v5_runtime.py'):
            updated = original.replace('        analytic_grasp_v1: bool = False,',
                '        analytic_grasp_v1: bool = False,\n        analytic_side_route_v1: bool = False,')
            updated = updated.replace('        self.analytic_grasp_v1 = analytic_grasp_v1',
                '        self.analytic_grasp_v1 = analytic_grasp_v1\n        self.analytic_side_route_v1 = analytic_side_route_v1')
        else:
            updated = original.replace('"analytic_grasp_v1", "grasp_rim_v1"',
                '"analytic_grasp_v1", "analytic_side_route_v1", "grasp_rim_v1"')
            updated = updated.replace('    parser.add_argument("--analytic-grasp-v1", action="store_true")',
                '    parser.add_argument("--analytic-grasp-v1", action="store_true")\n    parser.add_argument("--analytic-side-route-v1", action="store_true")')
        if updated == original:
            raise ValueError(f'flag wiring missing in {name}')
        path.write_text(updated)
        changed.append(name)
    names = list(dict.fromkeys([*[r['relative_path'] for r in parent['files']], *changed]))
    archive_path = Path(str(source) + '.tar')
    with tarfile.open(parent['archive']['path']) as archive:
        members = list(dict.fromkeys([*archive.getnames(), *changed]))
    with tarfile.open(archive_path, 'x') as archive:
        for name in members:
            archive.add(source / name, arcname=name, recursive=False)
    snapshot = {**parent, 'path': str(source), 'archive': ref(archive_path),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(source / name), 'relative_path': name} for name in names],
        'purpose': ('public measured tangent-axis entry avoids pushing the target with an open finger; contact geometry and servo tolerances unchanged'
                    if args.revision == 3 else
                    'public measured furniture side staging; contact geometry and servo tolerances unchanged')}
    (source / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    # Use the registered snapshot itself for the CPU checks.
    cpu = subprocess.run([str(ROOT / '.venv/bin/python'), '-m', 'pytest',
        'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py',
        'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py', '-q'], cwd=source,
        env={**os.environ, 'PYTHONPATH': str(source)}, capture_output=True, text=True)
    (source / 'side_route_tests.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    plan = json.loads(PRIOR.read_text())
    method = 'analytic_side_route'
    condition = copy.deepcopy(next(iter(plan['conditions'].values())))
    condition['overrides']['analytic_side_route_v1'] = True
    cases = [{**c, 'name': c['name'] + '_side_route', 'condition': method} for c in plan['cases']]
    adapter = Path(plan['adapter_path'])
    prep = output / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    producer.write_bytes(Path(__file__).read_bytes())
    plan.update(source_path=str(source), source_snapshot=snapshot, source_commit=snapshot['commit'],
        conditions={method: condition}, cases=cases, method=method, producer=ref(producer),
        producer_dependencies=[ref(producer), *[ref(adapter / 'scripts' / name) for name in
            ('probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
             'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
        references=[*plan['references'], ref(PRIOR)],
        purpose='paired three cabinet descent failures; public side staging only',
        confirmation=False, training_allowed=False, private_labels_used_for_control=False)
    manifest = prep / 'selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
        'PERTURB_SKILL_SOURCE': str(source), 'PERTURB_SKILL_ADAPTER': str(adapter),
        'PERTURB_SKILL_OUTPUT': str(output), 'PERTURB_SKILL_STARTUP': '1'}
    launcher = adapter / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    cpu = subprocess.run(['bash', str(launcher)], cwd='/tmp', env={**os.environ, **env,
        'PERTURB_SKILL_CPU_ONLY': '1'}, text=True, capture_output=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    command = ['sbatch', '--parsable', '--array=0', '--nice=0',
        '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
    job = subprocess.check_output(command, cwd='/tmp', text=True).strip()
    (prep / 'startup_submission.json').write_text(json.dumps({'job': job, 'command': command,
        'environment': env, 'manifest': ref(manifest), 'launcher': ref(launcher),
        'physical_startup': 'pending', 'confirmation': False}, indent=2) + '\n')
    print(json.dumps({'job': job, 'manifest': ref(manifest), 'cases': 3}), flush=True)


if __name__ == '__main__':
    main()
