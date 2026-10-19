# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Submit the registered original forks after their shared-service startup."""

import argparse
import hashlib
import itertools
import json
import os
import subprocess
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--startup-output', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    preparation = args.preparation.resolve(strict=True)
    receipt = preparation/'full_submission.json'
    if receipt.exists():
        raise ValueError('use the existing submission receipt')
    prep = read(preparation/'preparation.json')
    start = read(args.startup_output/'startup_proof.json')
    plan = read(preparation/'batch_plan.json')
    startup = read(preparation/'startup_plan.json')['batches'][0]
    if (start['source_commit'] != prep['source_commit'] or start['manifest'] != prep['manifest']
            or start['launcher'] != prep['launcher'] or start['indices'] != startup['indices']):
        raise ValueError('startup did not use the registered source, launcher and cases')
    if start['worker_errors'] or len(start['physical_requests']) != len(startup['indices']):
        raise ValueError('every representative category needs a real physical request')
    for ref in (prep['manifest'], prep['launcher']):
        if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('registered file changed')
    levels = list(args.startup_output.glob('N*/episodes.jsonl'))
    if len(levels) != 1:
        raise ValueError('expected one real startup level')
    rows = [json.loads(line) for line in levels[0].read_bytes().splitlines()]
    if len(rows) != len(startup['indices']) or not all(
            r['process_exit_code'] == 0 and r['result']['status'] == 'startup_physical' for r in rows):
        raise ValueError('startup workers did not all complete first physics')
    step = start['slurm_job_id']+'.'+start['slurm_step_id']
    accounting = subprocess.check_output(['sacct', '-n', '-j', step,
        '--format=JobIDRaw%32,JobID%32,State%32,ExitCode', '-P'], text=True)
    states = [row.strip().split('|') for row in accounting.splitlines()]
    if not any(row[0] == step and row[2:] == ['COMPLETED', '0:0'] for row in states):
        raise ValueError('startup Slurm step has not completed successfully: '+accounting)
    check_env = dict(os.environ, CUDA_VISIBLE_DEVICES='', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for index in range(len(plan['batches'])):
        subprocess.run([str(root/'.venv/bin/python'), prep['launcher']['path'], '--batch-plan',
            str(preparation/'batch_plan.json'), '--batch-index', str(index), '--preflight'],
            cwd=root, check=True, env=check_env, stdout=subprocess.DEVNULL)
    queue = [line.split('|') for line in subprocess.check_output(['squeue', '-r', '-h',
        '-u', 'sunyihan', '-o', '%i|%j|%T|%N|%R|%b'], text=True).splitlines()]
    c2 = [r for r in queue if r[1].startswith(('rd-bounded-choice-', 'rd-c2-'))
        and r[2] in {'RUNNING', 'PENDING'} and 'gpu' in r[5].lower()]
    active = [r for r in queue if r[1].startswith('rd-bounded-')
        and not r[1].startswith('rd-bounded-choice-') and r[2] == 'RUNNING']
    if len(active) > 4 or any(r[3] != 'node02' for r in active):
        raise ValueError('unexpected C3 resource state')
    cap = 3 if c2 else 4
    dependency = ('?'.join('afterany:'+':'.join(r[0] for r in group)
        for group in itertools.combinations(active, len(active)-cap+1)) if len(active) >= cap else None)
    command = ['sbatch', '--parsable', '--nodelist=node02', '--nice=500', '--export=ALL',
        '--array=0-'+str(len(plan['batches'])-1)+'%'+str(max(1, cap-len(active))),
        *(['--dependency='+dependency] if dependency else []),
        str(Path(prep['launcher']['path']).parent/'run_shared_batch_20261019.sbatch')]
    env = dict(os.environ, BATCH_PLAN=str(preparation/'batch_plan.json'),
        LAUNCHER=prep['launcher']['path'], STARTUP='0', RESULTS_ROOT=str(preparation.parent))
    job = subprocess.check_output(command, cwd=root, env=env, text=True).strip().split(';')[0]
    value = {'job': job, 'command': command, 'source_commit': prep['source_commit'],
        'manifest': prep['manifest'], 'launcher': prep['launcher'], 'startup_proof': str(
            args.startup_output/'startup_proof.json'), 'startup_step': step,
        'aggregate_cap': cap, 'codex2_gpu': c2, 'cpu_per_job': 20, 'memory_per_job_gb': 140,
        'training': False, 'confirmation': False}
    with receipt.open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
