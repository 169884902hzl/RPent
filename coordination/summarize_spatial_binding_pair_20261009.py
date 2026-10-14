"""Pair the ten fixed spatial episodes, retaining startup and any faults."""

from collections import Counter
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
RUN = ROOT / 'results/harness_v5/spatial_transfer_binding_A3_paired10_20261009_r1'
PREP = RUN / 'preparation/A3-N'
BASELINE = ROOT / 'artifacts/skill_budget_A3N80_complete_20261009_r1/episodes.jsonl'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def key(episode):
    return tuple(episode[k] for k in ('suite', 'task', 'seed'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    run = args.run_root
    prep = run / 'preparation/A3-N'
    index = json.loads((prep / 'manifest.json').read_text())
    expected = {}
    refs = [ref(prep / 'manifest.json'), ref(BASELINE), ref(Path(__file__))]
    for item in index['files']:
        p = Path(item['path'])
        if ref(p) != item:
            raise ValueError('registered plan changed')
        for e in json.loads(p.read_text())['episodes']:
            if key(e) in expected:
                raise ValueError('duplicate registered episode')
            expected[key(e)] = e
    if len(expected) != 10:
        raise ValueError('expected same spatial task0-4/init40,41')
    baseline = {key(r['episode']): r for r in map(json.loads, BASELINE.read_text().splitlines())
                if r['episode']['suite'] == 'libero_spatial_task'}
    if baseline.keys() != expected.keys():
        raise ValueError('baseline episodes differ')
    records, faults, tails = {}, [], []
    for ledger in sorted((run / 'A3-N').glob('**/probe/episodes.jsonl')):
        raw = ledger.read_bytes()
        boundary = raw.rfind(b'\n') + 1
        if len(raw) > boundary:
            tails.append({'path': str(ledger), 'bytes': len(raw) - boundary})
        refs.append(ref(ledger))
        for line in raw[:boundary].splitlines():
            row = json.loads(line)
            ident = key(row['episode'])
            if ident not in expected:
                raise ValueError('unregistered result')
            result = row['result']
            if result.get('status') in ('startup', 'startup_error') or result.get('infrastructure_failure'):
                faults.append(row)
                continue
            if ident in records:
                raise ValueError('duplicate functional result')
            choices = Path(row['output_dir']) / 'choices.jsonl'
            events = [json.loads(line) for line in choices.read_text().splitlines() if line.strip()]
            spending, causes = Counter(), Counter()
            for event in events:
                receipt = event.get('receipt') or {}
                spending[receipt.get('tool', event['selected'].partition('(')[0])] += receipt.get('sim_steps_used', 0)
                if receipt.get('verification') in ('failed', 'execution_error', 'task_not_completed', 'unmeasured'):
                    causes[str(receipt.get('failure_reason') or receipt.get('verification'))] += 1
            records[ident] = {**row, 'trace': ref(choices), 'skill_sim_steps': dict(spending),
                             'failure_receipts': dict(causes)}
    pairs, matrix = [], Counter()
    for ident, episode in expected.items():
        old = baseline[ident]['result'].get('official_success')
        current = records.get(ident)
        new = current['result'].get('official_success') if current else None
        pair = {'episode': episode, 'baseline_success': old, 'current_success': new,
            'termination_category': current['result'].get('termination_category') if current else None,
            'skill_sim_steps': current['skill_sim_steps'] if current else None,
            'failure_receipts': current['failure_receipts'] if current else None,
            'trace': current['trace'] if current else None}
        pairs.append(pair)
        if isinstance(new, bool):
            matrix[f'old{int(old)}_new{int(new)}'] += 1
    improved, regressed = matrix['old0_new1'], matrix['old1_new0']
    flips = improved + regressed
    pvalue = min(1., 2 * sum(math.comb(flips, i) for i in range(min(improved, regressed) + 1)) / 2**flips) if flips else 1.
    args.output.mkdir(parents=True, exist_ok=False)
    paths = []
    for name, data in (('episodes', records.values()), ('paired', pairs), ('infrastructure_attempts', faults)):
        path = args.output / (name + '.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in data))
        paths.append(ref(path))
    report = {'registered': 10, 'recorded': len(records), 'pending': 10 - len(records),
        'baseline_success': sum(r['result'].get('official_success') is True for r in baseline.values()),
        'current_success': sum(r['result'].get('official_success') is True for r in records.values()),
        'paired_counts': dict(matrix), 'improved': improved, 'regressed': regressed,
        'exact_mcnemar_p': pvalue, 'source_commit': index['source_commit'],
        'median_wall_s': statistics.median(r['result']['wall_s'] for r in records.values()
            if isinstance(r['result'].get('wall_s'), (float, int))) if any(
                isinstance(r['result'].get('wall_s'), (float, int)) for r in records.values()) else None,
        'fault_attempts': len(faults), 'unclosed_tails': tails, 'files': paths, 'inputs': refs,
        'run_root': str(run),
        'one_changed_behavior': 'instruction_transfer_binding_v1 public source-target macro priority; implementation pinned by source snapshot',
        'other_runtime_flags_unchanged': True, 'confirmation': False, 'training_allowed': False,
        'scope': 'paired development; ten episodes do not establish general effectiveness'}
    p = args.output / 'manifest.json'
    p.write_text(json.dumps(report, indent=2) + '\n')
    lines = ['| task/init | old/new | skill sim steps | end |', '|---|---|---|---|']
    for row in pairs:
        e = row['episode']
        lines.append(f"| {e['task']}/{e['seed']} | {int(row['baseline_success'])}/{row['current_success']} | "
            + ', '.join(f'{name}:{value}' for name, value in (row['skill_sim_steps'] or {}).items())
            + f" | {row['termination_category']} |")
    (args.output / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'manifest': ref(p), **{k: report[k] for k in ('recorded', 'pending',
        'baseline_success', 'current_success', 'improved', 'regressed', 'exact_mcnemar_p')}}))


if __name__ == '__main__':
    main()
