"""Wait on running4254; inspect exact status/attempt paths and report faults."""

import json
from pathlib import Path
import subprocess
import time

from monitor_job4254_cpu import BASE, JOB, ROOT, command


offsets = {}
last_summary = time.monotonic()
while True:
    raw = command(['sacct', '-j', '4254', '--format=JobID,State,ExitCode,Elapsed', '-P'])
    states = [dict(zip(raw.splitlines()[0].split('|'), line.split('|')))
              for line in raw.splitlines()[1:] if line.strip() and '.' not in line.split('|')[0]]
    failures = [s for s in states if s['State'] not in ('RUNNING', 'PENDING', 'COMPLETING', 'COMPLETED')
                or s['State'] == 'COMPLETED' and s['ExitCode'] != '0:0']
    counts, alerts = [], []
    for part in range(8):
        path = JOB / f'part{part}/infrastructure_attempts.jsonl'
        if path.is_file():
            with path.open('rb') as stream:
                stream.seek(offsets.get(part, 0))
                data = stream.read()
                boundary = data.rfind(b'\n') + 1
                offsets[part] = offsets.get(part, 0) + boundary
            for line in data[:boundary].splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get('infrastructure_failure') or row.get('raised_error'):
                    alerts.append({'part': part, 'path': str(path), 'case': row['case']['name'],
                                   'attempt_index': row.get('attempt_index'), 'status': row.get('status'),
                                   'raised_error': row.get('raised_error'), 'error_stage': row.get('error_stage'),
                                   'output_dir': row.get('output_dir'),
                                   'infrastructure_failure': row.get('infrastructure_failure'),
                                   'private_diagnostic_error': (row.get('first_attempt') or {}).get('private_diagnostic_error')})
        ledger = JOB / f'part{part}/episodes.jsonl'
        if ledger.is_file():
            with ledger.open('rb') as stream:
                n = sum(line.endswith(b'\n') and bool(line.strip()) for line in stream)
        else:
            n = 0
        counts.append({'part': part, 'recorded': n})
    complete = len(states) == 8 and all(s['State'] == 'COMPLETED' and s['ExitCode'] == '0:0' for s in states)
    event = {'sacct': states, 'record_counts': counts, 'infrastructure_or_exception_alerts': alerts,
             'failed_shards': failures, 'complete': complete}
    print(json.dumps(event), flush=True)
    if complete or failures or alerts:
        script = BASE / 'monitor_job4254_cpu.py'
        result = subprocess.run([str(ROOT / '.venv/bin/python'), str(script)] + (['--final'] if complete else []),
                                capture_output=True, text=True)
        print(json.dumps({'terminal_monitor_stdout': result.stdout, 'stderr': result.stderr,
                          'returncode': result.returncode}), flush=True)
        if failures:
            for failure in failures:
                part = failure['JobID'].split('_')[-1]
                log = ROOT / f'results/slurm-4254_{part}.log'
                print(json.dumps({'failed_log': str(log), 'tail': log.read_text(errors='replace')[-6000:]
                                  if log.is_file() else None}), flush=True)
        break
    if time.monotonic() - last_summary >= 600:
        print(command([str(ROOT / '.venv/bin/python'), str(BASE / 'monitor_job4254_cpu.py')]), flush=True)
        last_summary = time.monotonic()
    # This interval waits only on the explicitly running GPU dependency.
    time.sleep(60)
