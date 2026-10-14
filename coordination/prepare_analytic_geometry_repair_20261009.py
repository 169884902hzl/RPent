"""Pin cup-rim and pan-handle geometry; preserve the prior guard failures."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'source_v5_contact_methods_20261009_r2'
SOURCE = ROOT / 'source_v5_contact_methods_20261009_r4'
PREVIOUS = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r2'
OUTPUT = ROOT / 'results/harness_v5/perturb_contact_methods_selection_20261009_r4'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent = json.loads((PARENT / 'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path'])) != parent['archive']:
        raise ValueError('parent snapshot changed')
    shutil.copytree(PARENT, SOURCE, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    changed = ['robots/libero/v5_analytic_grasp.py', 'tests/unit_tests/robots/libero/test_v5_analytic_grasp.py']
    for relative in changed:
        shutil.copy2(ROOT / relative, SOURCE / relative)
    with tarfile.open(parent['archive']['path']) as archive:
        names = list(dict.fromkeys([*archive.getnames(), *changed]))
    archive_path = Path(str(SOURCE) + '.tar')
    with tarfile.open(archive_path, 'x') as archive:
        for relative in names:
            archive.add(SOURCE / relative, arcname=relative, recursive=False)
    snapshot = {**parent, 'path': str(SOURCE), 'archive': ref(archive_path),
        'parent_snapshot': ref(PARENT / 'source_snapshot.json'),
        'files': [{**ref(SOURCE / r['relative_path']), 'relative_path': r['relative_path']}
                  for r in parent['files']],
        'purpose': 'analytic v2 measured cup rim/pan handle, no Pi0.5 handoff changes'}
    with tarfile.open(archive_path) as archive:
        for relative in changed:
            if hashlib.sha256(archive.extractfile(relative).read()).hexdigest() != ref(SOURCE / relative)['sha256']:
                raise ValueError('archive mismatch')
    (SOURCE / 'source_snapshot.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    for category in ('cup', 'frypan'):
        old_prep = PREVIOUS / f'grasp_{category}_analytic/preparation'
        old = json.loads((old_prep / 'startup_submission.json').read_text())
        old_plan = Path(old['manifest']['path'])
        if ref(old_plan) != old['manifest']:
            raise ValueError('prior plan changed')
        cell = f'grasp_{category}_analytic_v2'
        prep = OUTPUT / cell / 'preparation'
        prep.mkdir(parents=True, exist_ok=False)
        producer = prep / 'producer.py'
        producer.write_bytes(Path(__file__).read_bytes())
        plan = json.loads(old_plan.read_text())
        cases = [{**case, 'name': case['name'] + '_v2', 'condition': 'analytic_v2'} for case in plan['cases']]
        plan.update(source_path=str(SOURCE), source_snapshot=snapshot, cases=cases,
            conditions={'analytic_v2': plan['conditions']['analytic']}, method='analytic_v2',
            producer=ref(producer), producer_dependencies=[ref(producer),
                *[r for r in plan['producer_dependencies'] if r['path'] != plan['producer']['path']]],
            references=[*plan['references'], ref(old_plan)],
            prior_method_diagnostic_retained={'job': old['job'], 'reason': 'whole-body width exceeds aperture; measured rim/handle needed'})
        # The mutable original producer is retained only as historical
        # evidence in the unchanged previous plan, never as a live dependency.
        plan['producer_dependencies'] = [ref(producer),
            *[r for r in plan['producer_dependencies'][1:]
              if Path(r['path']).name != 'prepare_contact_methods_selection_20261009.py']]
        manifest = prep / 'selection.json'
        manifest.write_text(json.dumps(plan, indent=2) + '\n')
        env = dict(old['environment'])
        env.update(PERTURB_SKILL_PLAN=str(manifest), PERTURB_SKILL_PLAN_SHA=ref(manifest)['sha256'],
                   PERTURB_SKILL_SOURCE=str(SOURCE), PERTURB_SKILL_OUTPUT=str(OUTPUT / cell))
        launcher = Path(old['launcher']['path'])
        cpu = subprocess.run(['bash', str(launcher)], capture_output=True, text=True,
            env={**os.environ, **env, 'PERTURB_SKILL_CPU_ONLY': '1'})
        (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
        cpu.check_returncode()
        result = subprocess.run(['sbatch', '--parsable', '--array=0', '--nice=0',
            '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)],
            capture_output=True, text=True, check=True)
        record = {'job': result.stdout.strip(), 'environment': env, 'manifest': ref(manifest),
            'launcher': ref(launcher), 'CPU_preflight': 'pass', 'physical_startup': 'pending',
            'confirmation': False}
        (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'cell': cell, 'job': record['job'], 'registered': len(cases)}), flush=True)


if __name__ == '__main__':
    main()
