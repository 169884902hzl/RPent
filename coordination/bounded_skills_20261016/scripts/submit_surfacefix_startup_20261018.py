"""Replay the recorded false-cutoff state before admitting a new source array."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
reports = root/'coordination/bounded_skills_20261016/reports'
tag = 'chunk_v2_surfacefix_20261018'
receipt = reports/f'{tag}_startup_submission.json'
assert not receipt.exists(), 'Reuse the saved submission receipt'
prep = json.loads((reports/f'{tag}_preparation.json').read_text())
source, manifest = Path(prep['snapshot']), Path(prep['manifest']['path'])
launcher = source/'scripts/run_bounded_21f0744_20261017.sbatch'
assert all(p.is_absolute() and p.is_file() for p in (manifest, launcher))
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == prep['manifest']['sha256']
queue = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N|%b|%R'], text=True)
rows = [line.split('|') for line in queue.splitlines()]
ours = [r for r in rows if r[1].startswith('rd-bounded-') and not r[1].startswith('rd-bounded-choice-')]
running = [r for r in ours if r[2] == 'RUNNING']
assert len(running) <= 4 and all(r[3] == 'node02' for r in running)
# This startup replaces a future v2 slot, never a currently running task.
# RF/C5/C6/Codex2 and historical held jobs are outside this update.
throttle = ['scontrol', 'update', 'JobId=8300', 'ArrayTaskThrottle=1']
subprocess.run(throttle, check=True)
arguments = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--array=24%1',
    '--export=ALL,SOURCE='+str(source)+',SOURCE_COMMIT='+prep['source_commit']+
    ',MANIFEST='+str(manifest)+',STARTUP=1,PAIR_LEGACY=0', str(launcher)]
job = subprocess.check_output(arguments, text=True).strip().split(';')[0]
report = {'job': job, 'mode': 'startup', 'source_commit': prep['source_commit'],
    'snapshot': str(source), 'manifest': prep['manifest'], 'arguments': arguments,
    'queue_before': rows, 'updates': [throttle], 'training': False, 'confirmation': False,
    'same_state_as': '8288_24', 'old_running_tasks_cancelled': False}
receipt.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'job': job, 'snapshot': str(source), 'mode': 'startup'}))
