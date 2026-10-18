"""Admit startup-gated original-state pairs and honor the returning C2 lane."""
import argparse
import itertools
import json
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='chunk_v3_final_20261018')
parser.add_argument('--indices', default='0,24,40')
parser.add_argument('--following-tag', default='chunk_v2_brakejoin_20261018')
parser.add_argument('--replace-array', default='8600')
args = parser.parse_args()
tag = args.tag
receipt = json.loads((base/'reports'/f'{tag}_startup_submission.json').read_text())
startup = receipt['job']+'_24'
full_path = base/'reports'/f'{tag}_full_submission.json'
last = None
last_accounting = 0.
while True:
    rows = [line.split('|') for line in subprocess.check_output(['squeue','-r','-h','-u','sunyihan',
        '-o','%i|%j|%T|%N|%b|%E|%R'],text=True).splitlines()]
    c2 = [r for r in rows if r[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
        and r[2] in {'RUNNING','PENDING'} and 'gpu' in r[4].lower()]
    ours = [r for r in rows if r[1].startswith('rd-bounded-')
        and not r[1].startswith('rd-bounded-choice-')]
    active = [r for r in ours if r[2]=='RUNNING']
    cap = 3 if c2 else 4
    assert len(active)<=4 and all(r[3]=='node02' for r in active), active
    watched = [receipt['job']]
    if full_path.exists():
        watched.append(json.loads(full_path.read_text())['job'])
    accounting = [line.split('|') for line in subprocess.check_output(
        ['sacct', '-X', '-n', '-j', ','.join(watched),
         '--format=JobID%32,State%32,ExitCode', '-P'], text=True).splitlines()]
    failed = [row for row in accounting if row[1].split()[0] in {
        'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'BOOT_FAIL', 'DEADLINE'}]
    if failed or time.monotonic()-last_accounting >= 600:
        audit = dict(time_pacific=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
            jobs=accounting, failures=failed)
        with (base/'reports'/f'{tag}_monitor_sacct.jsonl').open('a') as stream:
            stream.write(json.dumps(audit)+'\n')
        print(json.dumps(dict(accounting_jobs=watched,
            states=dict(Counter(row[1] for row in accounting)), failures=failed)), flush=True)
        last_accounting = time.monotonic()
    if failed:
        for job, state, code in failed:
            log = root/'results'/f'slurm-{job.strip()}.log'
            if log.exists():
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size-12000))
                    print(stream.read().decode('utf8', 'replace'), flush=True)
        raise SystemExit('PHYSICAL_JOB_FAILED: inspect preserved log and repair before resubmission')
    pending_start = [r for r in ours if r[0]==startup and r[2]=='PENDING']
    if pending_start:
        dependency = ('?'.join('afterany:'+':'.join(row[0] for row in group)
            for group in itertools.combinations(active, len(active)-cap+1)) if len(active)>=cap else '')
        # Do not release held jobs. This startup was submitted as ordinary pending.
        assert 'JobHeld' not in pending_start[0][6]
        subprocess.run(['scontrol','update','JobId='+startup,'Dependency='+dependency],check=True)
    if not any(r[0]==startup for r in ours) and not full_path.exists():
        state = subprocess.check_output(['sacct','-X','-n','-j',startup,
            '--format=State,ExitCode','-P'],text=True).strip()
        if state != 'COMPLETED|0:0':
            print(json.dumps(dict(startup_failed=state,job=startup)),flush=True)
            print((root/'results'/f'slurm-{startup}.log').read_text()[-16000:],flush=True)
            raise SystemExit(1)
        command = [str(root/'.venv/bin/python'),str(base/'scripts/submit_chunk_v2_20261018.py'),
            '--tag',tag,'--full','--indices',args.indices,'--replace-array',args.replace_array]
        subprocess.run(command,check=True)
        continue  # Refresh the queue; these rows predate the submitted array.
    barrier = startup
    if full_path.exists():
        full = json.loads(full_path.read_text())['job']
        barrier = full
        subprocess.run([str(root/'.venv/bin/python'),str(base/'scripts/rebalance_chunk_v2_20261018.py'),
            '--tag',tag],check=True,stdout=subprocess.DEVNULL)
        if not any(r[0].split('_')[0]==full for r in ours):
            print(subprocess.check_output(['sacct','-X','-n','-j',full,
                '--format=JobID,State,ExitCode,Elapsed','-P'],text=True),flush=True)
            print('TIMING_ARRAY_FINISHED: inspect all physical rows and failures before proceeding',flush=True)
            break
    subprocess.run([str(root/'.venv/bin/python'),str(base/'scripts/rebalance_chunk_v2_20261018.py'),
        '--tag',args.following_tag,'--after',barrier],check=True,stdout=subprocess.DEVNULL)
    status = dict(startup=[r for r in ours if r[0]==startup], running=active,cap=cap,codex2=c2,
        full_job=full if full_path.exists() else None)
    if status != last:
        print(json.dumps(dict(time_pacific=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),**status)),flush=True)
        last = status
    time.sleep(60)
