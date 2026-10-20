"""Dispatch repaired D2 shards into capacity freed by the original forks.

Only the named original array and newly submitted D2 shards are owned here.
Historical held jobs and other projects are never changed.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def limits(cap, original_running, original_pending, secondary_active, remaining):
    """Reserve one D2 slot while originals queue, then use their freed slots."""
    reserve = max(secondary_active, int(remaining > 0))
    primary_throttle = max(1, cap-reserve)
    available = max(0, cap-original_running-secondary_active)
    if original_pending:
        available = min(available, max(0, 1-secondary_active))
    return primary_throttle, min(remaining, available)


def read(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--startup-output', type=Path, required=True)
    parser.add_argument('--original-array', required=True)
    parser.add_argument('--original-results', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    prep = read(args.preparation/'preparation.json')
    plan = read(args.preparation/'batch_plan.json')
    startup = read(args.startup_output/'startup_proof.json')
    expected = read(args.preparation/'startup_plan.json')['batches'][0]
    for key in ('source_commit', 'manifest', 'launcher'):
        if startup[key] != prep[key]:
            raise ValueError('startup and production differ: '+key)
    if (startup['indices'] != expected['indices'] or startup['worker_errors']
            or len(startup['physical_requests']) != len(expected['indices'])):
        raise ValueError('startup lacks real VLA physics for every registered case')
    for ref in (prep['manifest'], prep['launcher']):
        if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('registered input changed')
    step = startup['slurm_job_id']+'.'+startup['slurm_step_id']
    accounting = subprocess.check_output(['sacct', '-n', '-j', step,
        '--format=JobIDRaw%32,State%32,ExitCode', '-P'], text=True)
    if not any(row.strip().split('|') == [step, 'COMPLETED', '0:0']
               for row in accounting.splitlines()):
        raise ValueError('startup Slurm step is not completed0:0')
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1',
        OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for index in range(len(plan['batches'])):
        subprocess.run([str(Path(prep['source']).parent/'.venv/bin/python'),
            prep['launcher']['path'], '--batch-plan', str(args.preparation/'batch_plan.json'),
            '--batch-index', str(index), '--preflight'], check=True, env=environment,
            stdout=subprocess.DEVNULL)
    if args.preflight:
        print(json.dumps({'preflight': 'passed', 'source_commit': prep['source_commit'],
            'startup_step': step, 'batches': len(plan['batches'])}), flush=True)
        return 0
    registry = args.preparation/'dispatch.jsonl'
    submitted = [json.loads(line) for line in registry.read_text().splitlines()] if registry.exists() else []
    if any(value['batch_index'] != index or value['manifest'] != prep['manifest']
            or value['source_commit'] != prep['source_commit']
            for index, value in enumerate(submitted)):
        raise ValueError('existing dispatcher registry differs from the registered preparation')
    seen_errors = set()
    with registry.open('a') as stream:
        while True:
            queue = [line.split('|') for line in subprocess.check_output([
                'squeue', '-r', '-h', '-u', 'sunyihan', '-o', '%i|%j|%T|%N|%R|%b'],
                text=True).splitlines()]
            original = [r for r in queue if r[0].startswith(args.original_array+'_')]
            peers = [r for r in queue if r[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
                and r[2] in {'RUNNING', 'PENDING'} and 'gpu' in r[5].lower()]
            cap = 3 if peers else 4
            secondary = [r for r in queue if any(
                r[0].startswith(value['job']+'_') for value in submitted)]
            running = sum(r[2] == 'RUNNING' for r in original)
            pending = any(r[2] == 'PENDING' for r in original)
            primary_cap, to_submit = limits(cap, running, pending,
                len(secondary), len(plan['batches'])-len(submitted))
            if pending:
                subprocess.run(['scontrol', 'update', 'JobId='+args.original_array,
                    'ArrayTaskThrottle='+str(primary_cap)], check=True)
            for _ in range(to_submit):
                index = len(submitted)
                command = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500',
                    '--array='+str(index)+'%1', '--export=ALL',
                    str(Path(prep['launcher']['path']).parent/'run_shared_batch_20261019.sbatch')]
                env = dict(os.environ, BATCH_PLAN=str(args.preparation/'batch_plan.json'),
                    LAUNCHER=prep['launcher']['path'], STARTUP='0',
                    RESULTS_ROOT=str(args.preparation.parent))
                job = subprocess.check_output(command, env=env, text=True).strip().split(';')[0]
                value = {'batch_index': index, 'job': job, 'command': command,
                    'source_commit': prep['source_commit'], 'manifest': prep['manifest'],
                    'startup_step': step, 'training': False, 'confirmation': False}
                submitted.append(value)
                stream.write(json.dumps(value)+'\n')
                stream.flush()
                print(json.dumps({'submitted': value}), flush=True)
            errors = []
            accounting = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j',
                ','.join([args.original_array]+[value['job'] for value in submitted]),
                '--format=JobID,State,ExitCode,Elapsed'], text=True).strip().splitlines()
            allocation_errors = []
            for line in accounting:
                fields = line.split('|')
                if len(fields) >= 3 and fields[1] not in {'RUNNING', 'PENDING', 'COMPLETED', 'COMPLETING'}:
                    key = 'allocation:'+fields[0]+':'+fields[1]
                    if key not in seen_errors:
                        seen_errors.add(key)
                        allocation_errors.append({'job': fields[0], 'state': fields[1], 'exit_code': fields[2]})
            for root in (args.original_results, args.preparation.parent):
                for path in root.glob('job*/N*/*/worker_summary.json'):
                    if str(path) in seen_errors:
                        continue
                    try:
                        row = read(path)
                    except json.JSONDecodeError:
                        # A live worker may still be writing this file. Check
                        # it again on the next poll instead of losing dispatch.
                        continue
                    if row.get('exit_code'):
                        seen_errors.add(str(path))
                        errors.append({'path': str(path), 'error': row.get('error'),
                            'message': row.get('message')})
            finished = not original and not secondary and not to_submit and len(submitted) == len(plan['batches'])
            print(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'cap': cap,
                'original_running': running, 'original_pending': pending,
                'original_throttle': primary_cap, 'D2_active': secondary, 'codex2_gpu': peers,
                'accounting': accounting, 'new_allocation_errors': allocation_errors,
                'new_worker_errors': errors, 'finished': finished}), flush=True)
            if finished:
                return 0
            time.sleep(60)


if __name__ == '__main__':
    raise SystemExit(main())
