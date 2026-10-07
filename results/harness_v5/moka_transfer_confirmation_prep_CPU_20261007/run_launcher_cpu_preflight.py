"""Run every real visited-state launcher shard on CPU from /tmp."""

import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'preparation'
manifest = OUT / 'moka_original_public_placement_visited10.json'
launcher = ROOT / 'scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch'
plan = json.loads(manifest.read_text())
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
env = {**os.environ, 'MOKA_TRANSFER_SOURCE': plan['source_snapshot']['path'],
       'MOKA_TRANSFER_MANIFEST': str(manifest), 'MOKA_TRANSFER_MANIFEST_SHA': digest,
       'MOKA_TRANSFER_PREFLIGHT_ONLY': '1'}


def run(part):
    result = subprocess.run(['bash', str(launcher)], cwd='/tmp',
        env={**env, 'SLURM_ARRAY_TASK_ID': str(part)}, capture_output=True, text=True)
    (OUT / f'part{part}_preflight.stdout.json').write_text(result.stdout)
    (OUT / f'part{part}_preflight.stderr.log').write_text(result.stderr)
    value = {'part': part, 'returncode': result.returncode}
    if result.returncode:
        value['error'] = result.stderr[-3000:]
    else:
        checked = json.loads(result.stdout)
        value.update(state_hashes_checked=checked['state_hashes_checked'],
                     files_checked=len(checked['files_checked']))
    return value


entry = subprocess.run([str(ROOT / '.venv/bin/python'),
    str(ROOT / 'scripts/probe_v5_moka_transfer_public_20261007.py'), '--help'],
    cwd='/tmp', env={**env, 'PYTHONPATH': plan['source_snapshot']['path']},
    capture_output=True, text=True)
(OUT / 'runner_entry_cpu.stdout.log').write_text(entry.stdout)
(OUT / 'runner_entry_cpu.stderr.log').write_text(entry.stderr)
with ThreadPoolExecutor(max_workers=4) as workers:
    parts = list(workers.map(run, range(8)))
report = {'scope': 'Actual launcher eight-shard CPU preflight; no physics, model calls, GPU or Slurm',
          'manifest': {'path': str(manifest), 'sha256': digest},
          'launcher': {'path': str(launcher), 'sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()},
          'source_snapshot': plan['source_snapshot'], 'runner_entry_returncode': entry.returncode,
          'runner_entry_error': entry.stderr[-3000:] if entry.returncode else None,
          'parts': parts, 'passed': entry.returncode == 0 and all(p['returncode'] == 0 for p in parts),
          'registered_cases': 10, 'new_physics': 0, 'new_model_calls': 0, 'new_GPU_jobs': 0,
          'qualification_authorized': False}
(OUT / 'launcher_cpu_preflight_report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('passed', 'manifest', 'launcher', 'parts', 'runner_entry_returncode')}))
if not report['passed']:
    raise SystemExit(1)
