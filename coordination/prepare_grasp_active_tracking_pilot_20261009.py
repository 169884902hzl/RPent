"""Keep contact fixed; test active public body-coupling verification."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_grasp_public_tracking_20261009_r1'
SOURCE = ROOT / 'source_v5_grasp_public_tracking_20261009_r2'
PREVIOUS = ROOT / 'results/harness_v5/grasp_public_tracking_pilot8_20261009_r1/grasp_bottle_analytic_tracking/preparation/selection.json'
OUTPUT = ROOT / 'results/harness_v5/grasp_public_tracking_pilot8_20261009_r2/grasp_bottle_analytic_tracking_active'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent source changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    relative = 'robots/libero/v5_runtime.py'
    runtime = SOURCE / relative
    old = runtime.read_text()
    current = (ROOT / relative).read_text()
    start, end = '    def verify_independent_grasp(', '    def verify_grasp_measurement('
    begin, finish = old.index(start), old.index(end)
    runtime.write_text(old[:begin] + current[current.index(start):current.index(end)] + old[finish:])
    changed = [relative, 'robots/libero/v5_grasp_public_tracking.py',
               'tests/unit_tests/robots/libero/test_v5_grasp_public_tracking.py']
    for relative in changed[1:]:
        shutil.copy2(ROOT / relative, SOURCE / relative)
    with tarfile.open(parent['archive']['path']) as archive:
        names = list(dict.fromkeys([*archive.getnames(), *changed]))
    target = Path(str(SOURCE) + '.tar')
    with tarfile.open(target, 'x') as archive:
        for relative in names:
            archive.add(SOURCE / relative, arcname=relative, recursive=False)
    files = [r['relative_path'] for r in parent['files']]
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(target),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in dict.fromkeys([*files, *changed])],
        'purpose': 'unchanged analytic contact, active 4cm public body-coupling verification; selection diagnostic'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    prep = OUTPUT / 'preparation'
    prep.mkdir(parents=True, exist_ok=False)
    producer = prep / 'producer.py'
    producer.write_bytes(Path(__file__).read_bytes())
    plan = json.loads(PREVIOUS.read_text())
    condition = plan['conditions']['analytic_tracking']
    plan.update(source_path=str(SOURCE), source_snapshot=snapshot,
        cases=[{**c, 'name': c['name'] + '_active', 'condition': 'analytic_tracking_active'} for c in plan['cases']],
        conditions={'analytic_tracking_active': condition}, method='analytic_tracking_active',
        producer=ref(producer), producer_dependencies=[ref(producer),
            *[r for r in plan['producer_dependencies'] if r['path'] != plan['producer']['path']]],
        references=[*plan['references'], ref(PREVIOUS)],
        purpose='first8 public active-verifier diagnostic, not qualification; analytic contact unchanged',
        active_verification_translation_m=.04, truth_may_override_runtime=False)
    manifest = prep / 'selection.json'
    manifest.write_text(json.dumps(plan, indent=2) + '\n')
    adapter = Path(plan['adapter_path'])
    env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
        'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(adapter),
        'PERTURB_SKILL_OUTPUT': str(OUTPUT), 'PERTURB_SKILL_STARTUP': '1'}
    launcher = adapter / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    cpu = subprocess.run(['bash', str(launcher)], cwd='/tmp', env={**os.environ, **env,
        'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
    (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
    cpu.check_returncode()
    job = subprocess.check_output(['sbatch', '--parsable', '--array=0', '--nice=0',
        '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)], cwd='/tmp', text=True).strip()
    record = {'job': job, 'environment': env, 'manifest': ref(manifest), 'launcher': ref(launcher),
        'physical_startup': 'pending', 'confirmation': False}
    (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
