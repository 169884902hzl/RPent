"""Watch actual r16 jobs and release arrays after the existing physical check."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/public_servo_coupling_r16_selection_20261010_r1'
LOG = ROOT / 'coordination/public_servo_coupling_r16_watch_ledger_20261010.jsonl'
previous = None
while True:
    release = subprocess.run(['python3', str(ROOT / 'coordination/monitor_registered_grasp_v3r9.py')],
                             capture_output=True, text=True)
    if release.returncode:
        print(release.stdout + release.stderr, flush=True)
        raise SystemExit(release.returncode)
    jobs, formal_count = [], 0
    for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05'):
        prep = BASE / name / 'preparation'
        startup = json.loads((prep / 'submission.json').read_text())
        jobs.append(startup['startup_job'].split(';')[0])
        p = prep / 'formal_submission.json'
        if p.exists():
            jobs.append(json.loads(p.read_text())['formal_job'].split(';')[0])
            formal_count += 1
    status = subprocess.run(['sacct', '-X', '-n', '-P', '-j', ','.join(jobs),
        '-o', 'JobID,State,ExitCode'], capture_output=True, text=True, check=True).stdout.strip()
    if status != previous:
        record = {'utc_epoch_s': time.time(), 'jobs': jobs, 'formal_count': formal_count,
                  'sacct': status, 'monitor_output': release.stdout.strip()}
        with LOG.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        print(json.dumps(record), flush=True)
        previous = status
    lines = [line.split('|') for line in status.splitlines() if line.strip()]
    failures = [line for line in lines if line[1] in ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL')]
    if failures:
        print(json.dumps({'needs_repair': failures}), flush=True)
        raise SystemExit(1)
    all_jobs_visible = all(any(line[0] == job or line[0].startswith(job + '_')
                              for line in lines) for job in jobs)
    if formal_count == 3 and all_jobs_visible and lines and all(line[1] == 'COMPLETED' and line[2] == '0:0' for line in lines):
        print(json.dumps({'r16_all_jobs_completed': True, 'jobs': jobs}), flush=True)
        break
    # A real running/pending physical job is the dependency being awaited.
    time.sleep(30)
