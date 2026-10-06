"""Exercise all eight actual drawer559 launcher shards from /tmp on CPU."""

import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'preparation'
manifest = OUT / 'drawer559_native_original200_selection.json'
launcher = ROOT / 'scripts/run_v5_drawer559_native_selection.sbatch'
plan = json.loads(manifest.read_text())
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
env = {**os.environ, 'DRAWER559_SOURCE': plan['source_snapshot']['path'],
       'DRAWER559_MANIFEST': str(manifest), 'DRAWER559_MANIFEST_SHA': digest,
       'DRAWER559_BASE': str(OUT.parent / 'physical_native200'),
       'DRAWER559_PREFLIGHT_ONLY': '1'}


def run(part):
    result = subprocess.run(['bash', str(launcher)], cwd='/tmp',
                            env={**env, 'SLURM_ARRAY_TASK_ID': str(part)},
                            capture_output=True, text=True)
    (OUT / f'part{part}_preflight.stdout.json').write_text(result.stdout)
    (OUT / f'part{part}_preflight.stderr.log').write_text(result.stderr)
    if result.returncode:
        return {'part': part, 'returncode': result.returncode, 'error': result.stderr[-3000:]}
    value = json.loads(result.stdout)
    return {'part': part, 'returncode': 0, 'state_hashes_checked': value['state_hashes_checked'],
            'files_checked': len(value['files_checked']),
            'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest()}


with ThreadPoolExecutor(max_workers=4) as workers:
    parts = list(workers.map(run, range(8)))
report = {'scope': 'Actual registered launcher CPU preflight from/tmp, no model, physics, GPU or Slurm',
          'manifest': {'path': str(manifest), 'sha256': digest},
          'launcher': {'path': str(launcher), 'sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()},
          'source': plan['source_snapshot'], 'producer': plan['producer'],
          'runner': {'path': str(Path(__file__).resolve()), 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
          'parts': parts, 'passed': all(p['returncode'] == 0 for p in parts),
          'registered_cases': 200, 'source_files_checked_per_part': 24,
          'registered_type_counts': {'drawer_open': 100, 'drawer_close': 100},
          'source_archive_and_producer_checked_per_part': True,
          'new_physics': 0, 'new_model_calls': 0, 'new_GPU_jobs': 0,
          'qualification_authorized': False}
(OUT / 'launcher_cpu_preflight_report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'passed': report['passed'], 'manifest': report['manifest'],
                  'launcher': report['launcher'], 'parts': parts}))
if not report['passed']:
    raise SystemExit(1)
