"""Watch one registered development array and yield the borrowed fourth GPU."""

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--array', required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    seen_errors = set()
    while True:
        queue = [line.split('|') for line in subprocess.check_output([
            'squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N|%R|%b'],
            text=True).splitlines()]
        own = [r for r in queue if r[0].startswith(args.array+'_')]
        peers = [r for r in queue if r[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
            and r[2] in {'RUNNING', 'PENDING'} and 'gpu' in r[5].lower()]
        cap = 3 if peers else 4
        other_running = [r for r in queue if r[1].startswith('rd-bounded-')
            and not r[1].startswith('rd-bounded-choice-') and r[2] == 'RUNNING'
            and not r[0].startswith(args.array+'_')]
        if any(r[2] == 'PENDING' for r in own):
            subprocess.run(['scontrol', 'update', 'JobId='+args.array,
                'ArrayTaskThrottle='+str(max(1, cap-len(other_running)))], check=True)
        accounting = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j', args.array,
            '-o', 'JobID,State,ExitCode,Elapsed'], text=True).strip().splitlines()
        errors = []
        for path in args.results.glob('job'+args.array+'_*/N*/*/worker_summary.json'):
            row = json.loads(path.read_bytes())
            if row.get('exit_code') and str(path) not in seen_errors:
                seen_errors.add(str(path))
                errors.append({'path': str(path), 'error': row.get('error'), 'message': row.get('message')})
        print(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'array': args.array,
            'cap': cap, 'codex2_gpu': peers, 'accounting': accounting,
            'new_worker_errors': errors, 'finished': not own}), flush=True)
        if not own:
            return 0
        # Only the live registered array is awaited; no held jobs are released.
        time.sleep(30 if errors else 60)


if __name__ == '__main__':
    raise SystemExit(main())
