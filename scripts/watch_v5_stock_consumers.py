"""Close a stock service only when its explicitly registered consumers exit."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY',
            'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}


def consumers_exited(registry, states):
    """Missing registration or missing accounting remains an active dependency."""
    return bool(registry['registration_complete'] and registry['consumer_jobs']) and all(
        states.get(str(job), '').split()[0:1] and
        states[str(job)].split()[0] in TERMINAL
        for job in registry['consumer_jobs'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--registry-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.registry.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.registry_sha256:
        raise ValueError('consumer registry differs from registration')
    registry = json.loads(raw)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output/'events.jsonl').open('x') as events:
        previous = None
        while True:
            query = subprocess.run(['sacct', '-n', '-X', '-j',
                ','.join(str(j) for j in registry['consumer_jobs']),
                '--format=JobIDRaw,State,ExitCode', '--parsable2'],
                capture_output=True, text=True, timeout=20)
            states = {fields[0]: fields[1] for line in query.stdout.splitlines()
                      if len(fields := line.strip().split('|')) >= 3}
            current = (query.returncode, states, query.stderr)
            if current != previous:
                events.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                    'states': states, 'query_returncode': query.returncode,
                    'query_error': query.stderr})+'\n')
                events.flush()
                previous = current
            if query.returncode == 0 and consumers_exited(registry, states):
                marker = Path(registry['service_output'])/'EVALUATION_DONE'
                marker.write_text('All explicit registered consumers have terminal accounting states.\n')
                events.write(json.dumps({'event': 'normal_service_stop_requested',
                    'registry_sha256': args.registry_sha256, 'consumer_jobs': registry['consumer_jobs'],
                    'terminal_states': states, 'marker': str(marker)})+'\n')
                return
            time.sleep(20)


if __name__ == '__main__':
    main()
