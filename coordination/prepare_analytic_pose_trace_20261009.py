"""Replay three selected approach failures with read-only motion diagnostics."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_tracking_20261009_r3'
SOURCE = ROOT / 'source_v5_analytic_pose_trace_20261009_r1'
PREVIOUS = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r2/grasp_box_analytic/preparation/selection.json'
OUTPUT = ROOT / 'results/harness_v5/analytic_pose_trace3_20261009_r1/grasp_box_analytic_pose_trace'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['robots/libero/v5_analytic_grasp.py']
    for name in changed:
        shutil.copy2(ROOT / name, SOURCE / name)
    with tarfile.open(parent['archive']['path']) as archive:
        members = list(dict.fromkeys([*archive.getnames(), *changed]))
    target = Path(str(SOURCE) + '.tar')
    with tarfile.open(target, 'x') as archive:
        for name in members:
            archive.add(SOURCE / name, arcname=name, recursive=False)
    names = list(dict.fromkeys([*[r['relative_path'] for r in parent['files']], *changed]))
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(target),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in names],
        'purpose': 'read-only analytic pose motion trace; control parameters unchanged'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    plan = json.loads(PREVIOUS.read_text())
    requested = ['selection_reserve_grasp_box_9305009_analytic',
                 'selection_reserve_grasp_box_9305017_analytic',
                 'selection_grasp_box_9301210_analytic']
    by_name = {case['name']: case for case in plan['cases']}
    method = 'analytic_pose_trace'
    cases = [{**by_name[name], 'name': name + '_pose_trace', 'condition': method}
             for name in requested]
    condition = plan['conditions']['analytic']
    condition['overrides'].update(grasp_public_tracking_v1=True, motion_trace_v1=True)
    adapter = ROOT / 'coordination/perturb_contact_methods_adapter_20261009_r5'
    prep = OUTPUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    producer.write_bytes(Path(__file__).read_bytes())
    plan.update(source_path=str(SOURCE), source_snapshot=snapshot, source_commit=snapshot['commit'],
        adapter_path=str(adapter), cases=cases, conditions={method: condition}, method=method,
        producer=ref(producer), producer_dependencies=[ref(producer), *[ref(adapter / 'scripts' / name)
            for name in ('probe_v5_skill501_original.py', 'probe_v5_perturb_skill_20261009.py',
                         'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
        references=[*plan['references'], ref(PREVIOUS)], layout_states=3,
        diagnostic_contact_trajectory=True, private_labels_used_for_control=False,
        purpose='three retained selected descent failures; read-only contact/joint trace; no control change',
        confirmation=False, training_allowed=False)
    manifest = prep / 'selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
        'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(adapter),
        'PERTURB_SKILL_OUTPUT': str(OUTPUT), 'PERTURB_SKILL_STARTUP': '1'}
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
