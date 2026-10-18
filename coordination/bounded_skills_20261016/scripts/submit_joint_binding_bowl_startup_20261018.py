"""Queue the measured joint-binding replay in the first serial GPU lane."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = base/'reports/joint_binding_bowl_startup_submission_20261018.json'
assert not receipt.exists(), 'Read the existing submission rather than duplicating it'
prep = json.loads((base/'reports/handle_axis_preparation_20261018.json').read_text())
predecessor = json.loads((base/'reports/handle_axis_microwave_full_submission_20261018.json').read_text())['job'].split(';')[0]+'_140'
source, manifest = Path(prep['snapshot']), Path(prep['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == prep['manifest']['sha256']
environment = {**os.environ, 'PYTHONPATH': str(source), 'LIBERO_TYPE': 'standard',
    'LIBERO_CONFIG_PATH': str(root/'runtime_config'), 'CUDA_VISIBLE_DEVICES': '', 'OPENBLAS_NUM_THREADS': '1'}
preflight = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--shard-index', '14', '--shards', '220', '--states'],
    cwd=source, env=environment, capture_output=True, text=True)
log = base/'reports/joint_binding_bowl_startup_preflight_20261018.log'
log.write_text(preflight.stdout+preflight.stderr)
assert preflight.returncode == 0, preflight.stderr
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N'], text=True)
ours = [r.split('|') for r in queue.splitlines() if '|rd-bounded-' in r]
running = [r for r in ours if r[2] == 'RUNNING']
assert len(running) <= 3 and all(r[3] == 'node02' for r in running), running
command = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=14%1',
    '--dependency=afterany:'+predecessor,
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+prep['source_commit']+',MANIFEST='+str(manifest)+',STARTUP=1',
    str(source/'scripts/run_bounded_21f0744_20261017.sbatch')]
job = subprocess.check_output(command, text=True).strip()
report = {'scope': 'same-source original bowl init14 startup with public joint disambiguation',
    'job': job, 'arguments': command, 'preflight': {'exit_code': preflight.returncode, 'log': str(log)},
    'source_commit': prep['source_commit'], 'snapshot': str(source), 'manifest': prep['manifest'],
    'training': False, 'confirmation': False, 'pi05_disabled': True, 'lane': 1, 'aggregate_cap': 3,
    'queue_before': ours}
receipt.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: report[k] for k in ('job', 'source_commit', 'lane')}))
