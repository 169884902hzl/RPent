"""Exercise every real launcher shard from/tmp, without Slurm or GPU work."""

import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


OUT = Path(__file__).resolve().parent
manifest = OUT / 'pan_coupled_lift_confirmation100.json'
launcher = OUT / 'run_v5_pan556_confirmation100.sbatch'
sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
plan = json.loads(manifest.read_text())
env = {**os.environ, 'PANCONF_SOURCE':plan['source_snapshot']['path'],
    'PANCONF_MANIFEST':str(manifest),'PANCONF_MANIFEST_SHA':sha,'PANCONF_PREFLIGHT_ONLY':'1'}


def run(part):
    result = subprocess.run(['bash',str(launcher)],cwd='/tmp',env={**env,'SLURM_ARRAY_TASK_ID':str(part)},
        capture_output=True,text=True)
    (OUT/f'part{part}_preflight.stdout.json').write_text(result.stdout)
    (OUT/f'part{part}_preflight.stderr.log').write_text(result.stderr)
    if result.returncode:
        return {'shard':part,'returncode':result.returncode,'error':result.stderr[-2500:]}
    value = json.loads(result.stdout)
    return {'shard':part,'returncode':result.returncode,'state_hashes_checked':value['state_hashes_checked'],
        'files_checked':len(value['files_checked']), 'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest()}


with ThreadPoolExecutor(max_workers=4) as workers:
    parts = list(workers.map(run,range(8)))
report={'scope':'Actual launcher CPU-only preflight from/tmp; no physics, model calls, GPU or Slurm submission',
    'manifest':{'path':str(manifest),'sha256':sha},
    'launcher':{'path':str(launcher),'sha256':hashlib.sha256(launcher.read_bytes()).hexdigest()},
    'source':plan['source_snapshot'], 'parts':parts,
    'passed':all(p['returncode']==0 for p in parts),
    'registered_first_attempts':100,'distinct_states':99,'new_physics':0,'new_model_calls':0,'new_gpu_jobs':0}
(OUT/'launcher_cpu_preflight_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'parts':parts}))
if not report['passed']:
    raise SystemExit(1)
