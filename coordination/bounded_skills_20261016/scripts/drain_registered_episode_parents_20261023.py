"""Preserve running episode results before retiring two registered dispatchers.

Run on their compute node after only the dispatcher processes were stopped.
Episode processes and their owned policy/perception services keep running.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def close_dispatcher(row, registration):
    proc = Path('/proc')/str(row['pid'])
    parts = [x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
    assert proc.stat().st_uid == os.getuid()
    assert '--worker' not in parts
    assert parts[parts.index('--output')+1] == row['output']
    env = dict(x.split(b'=', 1) for x in (proc/'environ').read_bytes().split(b'\0') if b'=' in x)
    assert env[b'SLURM_JOB_ID'].decode() == row['job_id']
    panel = json.loads(Path(row['panel']['path']).read_bytes())
    assert reference(Path(row['panel']['path'])) == row['panel']
    closed = []
    for index in row['completed']+row['active_indices']:
        output = Path(row['output'])
        pointer = output/f'closed_{index:03d}.json'
        if pointer.exists():
            ref = json.loads(pointer.read_bytes())
            assert reference(Path(ref['summary']))['sha256'] == ref['sha256']
            closed.append(str(pointer))
            continue
        matches = sorted(output.glob(f'case{index:03d}*/summary.json'))
        assert len(matches) == 1, (index, matches)
        summary = matches[0]
        data = json.loads(summary.read_bytes())
        assert data['case'] == panel['jobs'][index]['case']
        assert data['source_commit'] == panel['source_commit']
        assert data['restored_original_subtask_start']['same_captured_physics']
        with pointer.open('x') as stream:
            json.dump({'summary': str(summary), 'sha256': reference(summary)['sha256'],
                'closure_recovered_from_finished_worker': reference(registration)}, stream)
        closed.append(str(pointer))
    subprocess.run(['scancel', row['job_id']], check=True)
    proof = {'registration': reference(registration), 'job_id': row['job_id'],
        'closed': closed, 'interrupted_episodes': 0}
    target = registration.with_name(f'redistribution4_drain_{row["job_id"]}_complete.json')
    with target.open('x') as stream:
        json.dump(proof, stream, indent=2)
    print(json.dumps({'retired_job': row['job_id'], 'preserved_cases': len(closed)}), flush=True)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.registration.read_bytes())
    target = args.registration.with_name('redistribution4_drain_complete.json')
    if target.exists():
        print(target.read_text(), flush=True)
        return
    previous = None
    finished = {}
    while len(finished) < len(plan['orchestrators']):
        pending = []
        for row in plan['orchestrators']:
            proof = args.registration.with_name(f'redistribution4_drain_{row["job_id"]}_complete.json')
            if proof.exists():
                finished[row['job_id']] = json.loads(proof.read_bytes())
                continue
            running = []
            for worker in (w for w in plan['active_workers'] if w['shard'] == row['shard']):
                summary = Path(worker['output'])/'summary.json'
                if summary.exists():
                    try:
                        json.loads(summary.read_bytes())
                        continue
                    except json.JSONDecodeError:
                        pass
                if not (Path('/proc')/str(worker['pid'])).exists():
                    raise RuntimeError('episode exited without a complete summary: '+str(worker))
                running.append(worker)
            if not running:
                finished[row['job_id']] = close_dispatcher(row, args.registration)
            pending.extend(running)
        if len(pending) != previous:
            print(json.dumps({'remaining_running_episodes': len(pending)}), flush=True)
            previous = len(pending)
        if pending:
            time.sleep(15)
    closed = [p for row in finished.values() for p in row['closed']]
    proof = {'registration': reference(args.registration), 'closed': closed,
        'completed_episodes_preserved': len(closed), 'interrupted_episodes': 0,
        'retired_jobs': [r['job_id'] for r in plan['orchestrators']],
        'reason': 'dispatcher redistribution only; all active workers wrote complete results',
        'training': False}
    with target.open('x') as stream:
        json.dump(proof, stream, indent=2)
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()
