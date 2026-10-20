"""Return one explicitly borrowed schema6 GPU when Codex2 queues a GPU job."""
import argparse
import datetime
import json
import subprocess
import time


def remote(host, command):
    return subprocess.check_output(['ssh', '-o', 'ConnectTimeout=15', host, command],
        text=True, timeout=45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='gpu5880-ts')
    parser.add_argument('--borrow-job', required=True, type=int)
    parser.add_argument('--ledger', required=True)
    args = parser.parse_args()
    pending_since = None
    cancelled = False
    with open(args.ledger, 'x', buffering=1) as ledger:
        while True:
            now = datetime.datetime.now().astimezone().isoformat()
            try:
                raw = remote(args.host, 'squeue -h -o "%i|%j|%T|%N|%b|%r"')
                rows = [line.split('|', 5) for line in raw.splitlines()]
                borrowed = next((row for row in rows if row[0] == str(args.borrow_job)), None)
                pending = [row[0] for row in rows if row[1].startswith('rd-c2-')
                    and row[2] == 'PENDING' and 'gpu' in row[4].lower() and row[5] != 'JobHeldUser']
                event = {'at': now, 'borrow_job': args.borrow_job,
                    'borrow_state': borrowed[2] if borrowed else 'not_in_queue', 'c2_pending': pending}
                if borrowed is not None:
                    if not borrowed[1].startswith('rd-c3-s6-') or borrowed[3] not in {'', 'node02'}:
                        raise ValueError('refuse to modify an unrecognized or non-node02 job')
                    if borrowed[2] == 'PENDING' and borrowed[5] == 'JobHeldUser':
                        raise ValueError('held jobs are outside this watcher scope')
                # A dependent job owns no GPU and can remain queued behind
                # Codex2's start. Recheck when it becomes eligible/running.
                dependency_wait = (borrowed is not None and borrowed[2] == 'PENDING'
                    and borrowed[5] == 'Dependency')
                if pending and borrowed is not None and not cancelled and not dependency_wait:
                    pending_since = now
                    remote(args.host, f'scancel {args.borrow_job}')
                    cancelled = True
                    event['action'] = 'cancel_explicit_borrowed_job_preserve_completed_cases'
                if borrowed is None:
                    event.update(done=True, cancellation_requested=cancelled, pending_first_seen=pending_since)
                ledger.write(json.dumps(event) + '\n')
                print(json.dumps(event), flush=True)
                if borrowed is None:
                    return 0
            except (subprocess.SubprocessError, OSError) as exc:
                ledger.write(json.dumps({'at': now, 'query_error': str(exc)}) + '\n')
                print(f'resource query failed: {exc}', flush=True)
            time.sleep(30)


if __name__ == '__main__':
    raise SystemExit(main())
