"""Add diagnostic contact trajectories to the unstarted rim/handle selections."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_contact_methods_20261009_r4'
SOURCE = ROOT / 'source_v5_contact_methods_20261009_r5'
OLD_ROOT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r4'
OUTPUT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r5'
ADAPTER = ROOT / 'coordination/perturb_contact_methods_adapter_20261009_r5'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    starts = [json.loads(p.read_text()) for p in sorted(OLD_ROOT.glob('*/preparation/startup_submission.json'))]
    if len(starts) != 2:
        raise ValueError('expected only cup/pan geometry startups')
    for old in starts:
        job = str(old['job']).split(';')[0]
        state = subprocess.check_output(['squeue', '-h', '-j', job, '-o', '%T'], text=True).strip()
        if state != 'PENDING':
            raise ValueError('old startup already running; preserve it and prepare separate later diagnosis')
        if any(Path(old['environment']['PERTURB_SKILL_OUTPUT']).glob('job*/part*/probe/episodes.jsonl')):
            raise ValueError('old startup has physical evidence')
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['scripts/probe_v5_skill501_original.py', 'tests/unit_tests/robots/libero/test_v5_skill501_original.py']
    for relative in changed:
        shutil.copy2(ROOT / relative, SOURCE / relative)
    with tarfile.open(parent['archive']['path']) as archive:
        names = list(dict.fromkeys([*archive.getnames(), *changed]))
    target = Path(str(SOURCE) + '.tar')
    with tarfile.open(target, 'x') as archive:
        for relative in names:
            archive.add(SOURCE / relative, arcname=relative, recursive=False)
    file_names = [r['relative_path'] for r in parent['files']]
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(target),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / name), 'relative_path': name} for name in dict.fromkeys([*file_names, *changed])],
        'purpose': 'same analytic v2 controls, private diagnostic contact trace only; no controller change'}
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    old_adapter = Path(starts[0]['environment']['PERTURB_SKILL_ADAPTER'])
    shutil.copytree(old_adapter, ADAPTER, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / changed[0], ADAPTER / changed[0])
    for old in starts:
        manifest_old = Path(old['manifest']['path'])
        plan = json.loads(manifest_old.read_text())
        if ref(manifest_old) != old['manifest']:
            raise ValueError('old plan changed')
        cell = manifest_old.parent.parent.name
        prep = OUTPUT / cell / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        producer.write_bytes(Path(__file__).read_bytes())
        plan.update(source_path=str(SOURCE), source_snapshot=snapshot, adapter_path=str(ADAPTER),
            producer=ref(producer), producer_dependencies=[ref(producer),
                *[ref(ADAPTER / 'scripts' / name) for name in ('probe_v5_skill501_original.py',
                    'probe_v5_perturb_skill_20261009.py', 'v5_perturb_goal_diagnostic.py', 'v5_perturb_public_reference.py')]],
            references=[*plan['references'], ref(manifest_old)],
            diagnostic_contact_trajectory=True, private_labels_used_for_control=False)
        manifest = prep / 'selection.json'
        manifest.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(old['environment'])
        env.update(PERTURB_SKILL_PLAN=str(manifest), PERTURB_SKILL_PLAN_SHA=ref(manifest)['sha256'],
                   PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_ADAPTER=str(ADAPTER),
                   PERTURB_SKILL_OUTPUT=str(OUTPUT / cell))
        launcher = ADAPTER / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
        cpu = subprocess.run(['bash', str(launcher)], env={**os.environ, **env,
            'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        result = subprocess.run(['sbatch', '--parsable', '--array=0', '--nice=0',
            '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)],
            capture_output=True, text=True, check=True)
        record = {'job': result.stdout.strip(), 'environment': env, 'manifest': ref(manifest),
            'launcher': ref(launcher), 'physical_startup': 'pending', 'confirmation': False,
            'replaces_unstarted_job': old['job']}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        subprocess.run(['scancel', str(old['job']).split(';')[0]], check=True)
        print(json.dumps({'cell': cell, 'job': record['job'], 'prior_unstarted': old['job']}), flush=True)


if __name__ == '__main__':
    main()
