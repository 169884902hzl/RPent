"""Return a running, explicitly registered resumable B2 shard on C2 demand."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time


def release_candidate(rows, priority):
    active = {'RUNNING', 'CONFIGURING', 'COMPLETING'}
    c3 = [r for r in rows if r[1].startswith('rd-c3-') and r[2] in active
        and r[3] == 'node02' and 'gpu' in r[4].lower()]
    c2 = [r for r in rows if r[1].startswith(('rd-c2-', 'rd-bounded-choice-'))
        and r[2] in {'PENDING', 'RUNNING', 'CONFIGURING'} and 'gpu' in r[4].lower()
        and r[5] not in {'JobHeldUser', 'JobHeldAdmin'}]
    chosen = next((r for job in priority for r in c3 if r[0] == str(job)
        and r[1].startswith('rd-c3-s6-B2-groups-') and r[2] != 'COMPLETING'), None)
    return (chosen[0] if chosen is not None and c2 and len(c3) > 3 else None,
            [r[0] for r in c3], [r[0] for r in c2])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs', type=Path, required=True)
    p.add_argument('--ledger', type=Path, required=True)
    a = p.parse_args()
    registered = json.loads(a.jobs.read_bytes())
    priority = registered['prefer_release']
    assert priority and all(str(job).isdigit() for job in priority)
    def remote(command):
        return subprocess.check_output(['ssh', '-o', 'ConnectTimeout=15', 'gpu5880-ts', command], text=True, timeout=45)
    cancelling = None
    with a.ledger.open('x', buffering=1) as ledger:
        while True:
            event = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            try:
                rows = [line.split('|', 5) for line in remote('squeue -u sunyihan -h -o "%i|%j|%T|%N|%b|%r"').splitlines()]
                candidate, running, c2 = release_candidate(rows, priority)
                event.update(c3_running=running, c2_demand=c2)
                if candidate is not None and cancelling not in running:
                    remote('scancel '+candidate)
                    cancelling = candidate
                    event.update(action='cancel_running_resumable_owned_shard', job=candidate)
                done = not any(row[0] in set(map(str, priority)) for row in rows)
                event['done'] = done
                ledger.write(json.dumps(event)+'\n')
                if done:
                    return
            except (OSError, subprocess.SubprocessError) as exc:
                ledger.write(json.dumps(dict(event, query_error=str(exc)))+'\n')
            time.sleep(30)


if __name__ == '__main__':
    main()
