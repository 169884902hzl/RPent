"""Give the v2 array the node02 slots naturally released by older oracle jobs."""
import argparse
import json
import subprocess
from itertools import combinations
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
parser.add_argument('--after', help='Let this already submitted startup finish before replacements')
args = parser.parse_args()
base = Path('/public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016')
receipt = json.loads((base/'reports'/f'{args.tag}_full_submission.json').read_text())
job = receipt['job']
raw = subprocess.check_output(['squeue', '-r', '-h', '-u', 'sunyihan',
    '-o', '%i|%j|%T|%N|%b|%E|%R'], text=True)
rows = [line.split('|') for line in raw.splitlines()]
codex2_gpu = [row for row in rows if row[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
    and row[2] in {'RUNNING', 'PENDING'} and 'gpu' in row[4].lower()]
aggregate_cap = 3 if codex2_gpu else 4
ours = [row for row in rows if row[1].startswith('rd-bounded-')
    and not row[1].startswith('rd-bounded-choice-')]
running = [row for row in ours if row[2] == 'RUNNING']
assert len(running) <= 4 and all(row[3] == 'node02' for row in running), running
other = [row for row in running if row[0].split('_')[0] != job]
capacity = max(1, aggregate_cap-len(other))
commands = []
deferred = []
if any(row[0].split('_')[0] == job for row in ours):
    # With three older tasks still running, a returning Codex2 GPU job
    # requires zero replacement shards until an older task naturally exits.
    # Array throttle zero means unlimited in Slurm, so use a real dependency.
    if args.after:
        dependency = 'afterany:'+args.after
    elif len(other) >= aggregate_cap:
        dependency = '?'.join('afterany:'+':'.join(row[0] for row in group)
            for group in combinations(other, len(other)-aggregate_cap+1))
    else:
        dependency = 'afterany:'+receipt['startup_proof']['job']
    command = ['scontrol', 'update', 'JobId='+job, 'ArrayTaskThrottle='+str(capacity)]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode and 'Job has already finished' in result.stderr:
        # A controller can finish between squeue and scontrol; Slurm settles
        # its array record independently of still-live child tasks.
        result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        if 'Job has already finished' not in result.stderr:
            raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
        deferred.append({'command':command,'reason':result.stderr.strip()})
    else:
        commands.append(command)
    # Once a shard is running, Slurm rejects Dependency on the parent ID.
    # Only change ordinary pending elements when the resource barrier changes.
    for row in ours:
        if row[0].split('_')[0] != job or row[2] != 'PENDING' or 'JobHeld' in row[6]:
            continue
        if len(other) < aggregate_cap and row[5] == '(null)' and not args.after:
            continue
        command = ['scontrol', 'update', 'JobId='+row[0], 'Dependency='+dependency]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            current = subprocess.check_output(['squeue','-h','-j',row[0],'-o','%T'],text=True).strip()
            if current != 'PENDING':
                deferred.append({'command':command,'reason':'state_changed_to_'+current})
                continue
            raise subprocess.CalledProcessError(result.returncode,command,result.stdout,result.stderr)
        commands.append(command)
report = {'time_pacific': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
    'job': job, 'our_running': running, 'other_running': other,
    'array_throttle': capacity, 'commands': commands, 'aggregate_cap': aggregate_cap,
    'deferred_queue_races':deferred,
    'codex2_gpu_jobs': codex2_gpu, 'fourth_card_borrow_permitted': not bool(codex2_gpu),
    'running_tasks_cancelled': False, 'protected_or_held_jobs_modified': False}
with (base/'reports'/f'{args.tag}_resource_rebalance.jsonl').open('a') as stream:
    stream.write(json.dumps(report)+'\n')
print(json.dumps(report))
