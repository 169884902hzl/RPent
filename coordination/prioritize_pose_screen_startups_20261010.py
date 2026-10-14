"""Temporarily delay this task's pending arrays until new startups run."""
import datetime
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUTPUT = ROOT / 'coordination/pose_screen_startup_priority_20261010_r2.jsonl'
BASE = ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r7'
STARTUPS = ['6135', '6136', '6137', '6138', '6139']


def log(record):
    with OUTPUT.open('a') as stream:
        stream.write(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), **record}) + '\n')


def main():
    jobs = []
    for path in sorted(BASE.glob('*/preparation/formal_submission.json')):
        job = json.loads(path.read_text())['formal_job'].split(';')[0]
        status = subprocess.run(['sacct', '-X', '-n', '-P', '-j', job, '-o', 'JobID,State,ExitCode'],
                                capture_output=True, text=True, check=True).stdout
        if any(line.split('|')[1] == 'PENDING' for line in status.splitlines() if '|' in line):
            jobs.append(job)
    held = []
    try:
        for job in jobs:
            result = subprocess.run(['scontrol', 'hold', job], capture_output=True, text=True)
            log({'action': 'temporary_hold_own_pending_array', 'job': job, 'returncode': result.returncode,
                 'stdout': result.stdout, 'stderr': result.stderr, 'running_trials_not_cancelled': True})
            result.check_returncode()
            held.append(job)
        start = time.monotonic()
        previous = None
        while time.monotonic() - start < 1800:
            status = subprocess.run(['sacct', '-X', '-n', '-P', '-j', ','.join(STARTUPS),
                '-o', 'JobID,State,ExitCode'], capture_output=True, text=True, check=True).stdout
            if status != previous:
                log({'action': 'startup_progress', 'status': status})
                print(status, flush=True)
                previous = status
            states = {line.split('|')[0]: line.split('|')[1] for line in status.splitlines() if '|' in line}
            if any(value in ('FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY') for value in states.values()):
                raise RuntimeError('new startup failure; release waiting arrays and repair immediately')
            if all(states.get(job) == 'COMPLETED' for job in STARTUPS):
                for job in STARTUPS:
                    contracts = list((ROOT / 'results/harness_v5/geometric_grasp_selection_20261010_r8').glob(
                        f'*/job{job}/part0/startup_contract.json'))
                    if len(contracts) != 1:
                        raise ValueError('one physical startup contract required per job')
                    contract = json.loads(contracts[0].read_text())
                    if contract['status'] != 'pass' or contract['physical_controls'] <= 0:
                        raise ValueError('actual physical startup did not pass')
                log({'action': 'five_real_physical_startups_completed'})
                break
            time.sleep(15)
        else:
            raise TimeoutError('startup priority window ended; release all delayed arrays')
    finally:
        for job in held:
            result = subprocess.run(['scontrol', 'release', job], capture_output=True, text=True)
            log({'action': 'release_own_array', 'job': job, 'returncode': result.returncode,
                 'stdout': result.stdout, 'stderr': result.stderr})
            result.check_returncode()


if __name__ == '__main__':
    main()
