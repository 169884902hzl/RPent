"""Compare recorded reruns, then export their own measured contexts to C2."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def wilson(k, n):
    z = 1.959963984540054
    c = (k/n + z*z/(2*n))/(1+z*z/n)
    h = z*math.sqrt(k*(n-k)/n**3 + z*z/(4*n*n))/(1+z*z/n)
    return [c-h, c+h]


def trial_key(trial):
    return trial['method'], trial.get('vla_variant', {}).get('name'), trial['trial_seed']


def stats(rows):
    n = len(rows)
    return {'n': n, 'before_success': sum(r['before_success'] for r in rows),
        'after_success': sum(r['after_success'] for r in rows),
        'improved': sum(r['improved'] for r in rows), 'regressed': sum(r['regressed'] for r in rows),
        'before_wilson95': wilson(sum(r['before_success'] for r in rows), n),
        'after_wilson95': wilson(sum(r['after_success'] for r in rows), n)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    registration = json.loads((args.run/'registration.json').read_bytes())
    registered = {r['case']: r for r in registration['rows']}
    baseline = {}
    parents = [('original90', base/'qualified90_9716b68c/CPU_closed90_r1')]
    parents += [(p, base/'layout_runtime_c7520ae1'/p/'CPU_closed_measured_r1')
        for p in ('measured_packet1', 'measured_packet2')]
    for domain, packet in parents:
        for line in (packet/'positions.jsonl').open():
            row = json.loads(line)
            worker = json.loads(Path(row['source']['path']).read_bytes())
            baseline[row['case']['name']] = (domain, row, worker['result'])
    closed, missing, pairs, mappings = {}, [], [], []
    for shard in range(2):
        plan_path = args.run/f'preparation/shard{shard}_physical_start.json'
        plan = json.loads(plan_path.read_bytes())
        for index, job in enumerate(plan['jobs']):
            name = job['case']['name']
            pointer = args.run/f'shard{shard}/closed_{index:03d}.json'
            if not pointer.exists():
                missing.append(name)
                continue
            entry = json.loads(pointer.read_bytes())
            raw_path = Path(entry['summary'])
            assert ref(raw_path)['sha256'] == entry['sha256']
            result = json.loads(raw_path.read_bytes())
            assert result['case'] == job['case'] and name not in closed
            assert result['source_commit'] == plan['source_commit']
            assert result['restored_original_subtask_start']['same_captured_physics']
            assert result['restored_original_subtask_start']['physics'] == registered[name]['after_initial']
            closed[name] = {'job': job, 'result': result, 'raw': ref(raw_path), 'shard': shard}
            domain, old_position, old = baseline[name]
            before = {trial_key(t): t for t in old['trials']}
            for trial in result['trials']:
                key = trial_key(trial)
                assert key in before, (name, key)
                previous = before[key]
                pairs.append({'case': name, 'domain': domain, 'category': job['case']['category'],
                    'method': key[0], 'variant': key[1], 'seed': key[2],
                    'before_success': previous['success'] is True, 'after_success': trial['success'] is True,
                    'improved': previous['success'] is not True and trial['success'] is True,
                    'regressed': previous['success'] is True and trial['success'] is not True,
                    'before_reason': previous['reason'], 'after_reason': trial['reason'],
                    'before_steps': previous['sim_steps'], 'after_steps': trial['sim_steps'],
                    'before': previous['choices'], 'after': trial['choices']})
            assert len(result['trials']) == len(old['trials']), name
            mappings.append({'case': name, 'domain': domain,
                'replaces_record_id': old_position['record_id'],
                'baseline_snapshot': registered[name]['baseline_snapshot'], 'new_raw': ref(raw_path),
                'operation': 'replace comparison with newly measured context; do not copy old self/VLA labels'})
    if missing:
        raise ValueError(f'not closed: {missing}')
    assert len(closed) == 155
    args.output.mkdir(parents=True, exist_ok=False)
    pair_path = args.output/'paired_trials.jsonl'
    pair_path.write_text(''.join(json.dumps(row)+'\n' for row in pairs))
    groups = defaultdict(list)
    for row in pairs:
        groups[(row['domain'], row['category'], row['method'], row['variant'])].append(row)
    report = {'states': len(closed), 'trials': len(pairs), 'summary': stats(pairs),
        'registered_initials_restored_exactly': True,
        'public_context_scope': 'fresh public reconstruction after exact physics restore; all new arms share that new request; no old context labels transferred',
        'by_group': [{'domain': k[0], 'category': k[1], 'method': k[2], 'variant': k[3], **stats(v)}
            for k, v in sorted(groups.items(), key=lambda item: str(item[0]))],
        'improvements': [r for r in pairs if r['improved']],
        'regressions': [r for r in pairs if r['regressed']],
        'failure_reasons': dict(Counter(r['after_reason'] for r in pairs if not r['after_success'])),
        'pairs': ref(pair_path), 'training_executed': False, 'PRO': False, 'D2': False, 'confirmation': False}
    write(args.output/'summary.json', report)
    write(args.output/'old_record_mapping.json', {'rows': mappings})
    if args.export:
        view = args.output/'raw_view'
        source_commit = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())['commit']
        for name, row in closed.items():
            directory = view/f"job{row['shard']}/N8"/name
            directory.mkdir(parents=True)
            (directory/name).symlink_to(Path(row['raw']['path']).parent/'episode', target_is_directory=True)
            write(directory/'worker_summary.json', {'case': row['job']['case'],
                'source_commit': source_commit, 'result': row['result'], 'raw_stage_summary': row['raw'],
                'registration': ref(args.run/'registration.json')})
        env = dict(os.environ, PYTHONPATH=str(args.source), CUDA_VISIBLE_DEVICES='',
            OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        for domain, _ in parents:
            command = [str(root/'.venv/bin/python'), str(args.source/'coordination/bounded_skills_20261016/scripts/export_original_schema6_measured_CPU_20261021.py'),
                '--source', str(args.source), '--manifest', str(args.run/f'preparation/{domain}_manifest.json'),
                '--results', str(view), '--policy-hashes', str(base/'qualified90_9716b68c/preparation/registered_pi05_hashes.sha256'),
                '--output', str(args.output/domain)]
            subprocess.run(command, env=env, check=True)
        print(json.dumps({'packages': [str(args.output/domain) for domain, _ in parents]}), flush=True)
    print(json.dumps({k: report[k] for k in ('states', 'trials', 'summary')}), flush=True)


if __name__ == '__main__':
    main()
