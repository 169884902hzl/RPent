"""Pair the registered thirty bounded episodes; keep VLA pilots out."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from aggregate_strict_latency_CPU_20261021 import arm, metrics, ref

INDICES = [*range(24), *range(26, 32)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    rows, missing = [], []
    for index in INDICES:
        roots = [p.parent for p in args.after.glob(f'shard*/closed_{index:03d}.json')]
        if not roots:
            missing.append(index)
            continue
        if len(roots) != 1:
            raise ValueError(f'duplicate closed state {index}: {roots}')
        before, after = arm(args.before, index, snapshot_digest), arm(roots[0], index, snapshot_digest)
        if before is None or after is None or before.get('continuation_pilot') or after.get('continuation_pilot'):
            raise ValueError('missing bounded baseline or pilot entered denominator')
        if before['case'] != after['case'] or before['initial_physics_sha256'] != after['initial_physics_sha256']:
            raise ValueError(f'pair {index} differs in full registered initial state')
        failures = []
        for line in Path(after['loops']['path']).read_bytes().splitlines():
            for receipt in json.loads(line)['receipts']:
                if receipt['outcome'] != 'success':
                    failures.append({key: receipt.get(key) for key in
                        ('skill', 'phase', 'stop_reason', 'steps_used', 'outcome')})
        rows.append({'index': index, 'case': before['case']['name'],
            'category': before['case'].get('category', before['case']['episode']['suite']),
            'before': before, 'after': after, 'failure_receipts': failures,
            'improved': not before['success'] and after['success'],
            'regressed': before['success'] and not after['success']})
    if missing and not args.allow_partial:
        raise ValueError(f'not closed: {missing}')
    if not rows:
        raise ValueError('no closed paired states')
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output/'paired_states.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    categories = defaultdict(list)
    for row in rows:
        categories[row['category']].append(row)
    report = {'scope': 'N1 same complete registered initial state; development only',
        'registered_bounded_indices': INDICES, 'excluded_continuation_pilots': [24, 25],
        'closed': len(rows), 'missing': missing, 'all_complete_initial_hashes_match': True,
        'before': metrics(rows, 'before'), 'after': metrics(rows, 'after'),
        'improvements': [r['case'] for r in rows if r['improved']],
        'regressions': [r['case'] for r in rows if r['regressed']],
        'categories': {category: {key: metrics(group, key) for key in ('before', 'after')}
            for category, group in categories.items()}, 'rows': ref(path), 'training': False}
    (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    text = ['| index | 状态 | 旧栈 | 修复后 | 决策数（旧→新） | 步数（旧→新） |',
        '|---:|---|---:|---:|---:|---:|']
    for row in rows:
        a, b = row['before'], row['after']
        text.append(f"| {row['index']} | {row['case']} | {int(a['success'])} | {int(b['success'])} | "
            f"{a['decisions']}→{b['decisions']} | {a['sim_steps']}→{b['sim_steps']} |")
    (args.output/'paired_table.md').write_text('\n'.join(text)+'\n')
    print(json.dumps({key: report[key] for key in ('closed', 'missing', 'before', 'after', 'regressions')}))


if __name__ == '__main__':
    main()
