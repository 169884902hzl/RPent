"""Let a critical replay use the next free card, then restore our queue."""

import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
REPLAY = '4877'
OWN_PENDING_ARRAYS = [4830, 4831, 4837, 4839, *range(4842, 4850),
                      *range(4852, 4856), *range(4857, 4862), *range(4878, 4883)]


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def main():
    output = ROOT / 'coordination/native_replay_queue_order_20261009.json'
    rows = run('squeue', '-h', '-r', '-u', 'sunyihan', '-t', 'PENDING',
               '-o', '%i|%E').splitlines()
    changed, events = [], []
    try:
        for row in rows:
            job, dependency = row.split('|', 1)
            if int(job.split('_')[0]) not in OWN_PENDING_ARRAYS:
                continue
            if dependency.strip() not in ('', '(null)'):
                raise ValueError(f'Unexpected existing dependency for {job}: {dependency}')
            run('scontrol', 'update', f'JobId={job}', f'Dependency=afterany:{REPLAY}')
            changed.append(job)
        events.append({'temporarily_ordered_after_replay': changed})
        output.write_text(json.dumps(events, indent=2) + '\n')
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            state = run('squeue', '-h', '-j', REPLAY, '-o', '%T').strip()
            if state != 'PENDING':
                events.append({'replay_state': state or 'finished'})
                break
            time.sleep(15)
    finally:
        for job in changed:
            result = subprocess.run(['scontrol', 'update', f'JobId={job}', 'Dependency='],
                                    capture_output=True, text=True)
            events.append({'restored': job, 'exit_code': result.returncode,
                           'stderr': result.stderr.strip()})
        output.write_text(json.dumps(events, indent=2) + '\n')


if __name__ == '__main__':
    main()
