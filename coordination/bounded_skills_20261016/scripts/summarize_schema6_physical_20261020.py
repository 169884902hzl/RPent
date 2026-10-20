"""Summarize registered schema6 pairs, keeping unknown and unfinished cases."""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.summarize_bounded_hybrid_d2 import rate, summarize


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'median': None, 'p90': None}
    at = .9 * (len(values) - 1)
    lo = int(at)
    hi = min(lo + 1, len(values) - 1)
    return {'n': len(values), 'median': statistics.median(values),
        'p90': values[lo] + (values[hi] - values[lo]) * (at - lo)}


def collect(root, plan):
    rows, pending = [], []
    for index, job in enumerate(plan['jobs']):
        pointer = root / f'closed_{index:03d}.json'
        if not pointer.exists():
            pending.append(index)
            continue
        entry = json.loads(pointer.read_bytes())
        path = Path(entry['summary'])
        reference = ref(path)
        if entry.get('sha256') and entry['sha256'] != reference['sha256']:
            raise ValueError(f'closed record changed: {path}')
        result = json.loads(path.read_bytes())
        if result['status'] not in {'physical_result', 'oracle_rule_uncovered'}:
            raise ValueError(f'nonfinal record in denominator: {path}')
        rows.append({'index': index, 'case': job['case'], 'source': reference, 'result': result})
    return rows, pending


def pair_summary(plan, rows):
    arms = ('default', 'original_variant') if plan['jobs'][0]['kind'] == 'move' else ('nudge', 'guarded')
    paired = []
    for row in rows:
        by_arm = {arm['arm']: arm for arm in row['result']['arms']}
        a, b = (by_arm[name] for name in arms)
        hashes = [branch.get('initial_physics_sha256') for branch in (a, b)]
        if None in hashes or hashes[0] != hashes[1]:
            raise ValueError(f'pair does not share full initial state: {row["source"]}')
        known = type(a.get('success')) is bool and type(b.get('success')) is bool
        paired.append({'index': row['index'], 'case': row['case']['name'],
            'category': row['case'].get('category'), 'source': row['source'],
            'initial_physics_hash_equal': True,
            'left': a, 'right': b, 'known_pair': known,
            'outcome_equal': a['success'] == b['success'] if known else None})
    groups = {}
    categories = ['all'] + sorted({row['category'] for row in paired if row['category']})
    for category in categories:
        group = paired if category == 'all' else [row for row in paired if row['category'] == category]
        registered = len(plan['jobs']) if category == 'all' else sum(
            job['case'].get('category') == category for job in plan['jobs'])
        known = [row for row in group if row['known_pair']]
        output = {'registered_pairs': registered, 'closed_pairs': len(group), 'known_pairs': len(known),
            'left_only_success': sum(row['left']['success'] and not row['right']['success'] for row in known),
            'right_only_success': sum(row['right']['success'] and not row['left']['success'] for row in known)}
        for side, name in zip(('left', 'right'), arms):
            outcomes = [row[side].get('success') for row in group] + [None] * (registered - len(group))
            output[name] = {'success': rate(outcomes)}
            for field in ('decisions', 'sim_steps', 'wall_s'):
                output[name][field] = distribution([row[side][field] for row in group if field in row[side]])
            output[name]['first_stop_reasons'] = dict(Counter(receipt.get('stop_reason', 'missing')
                for row in group for receipt in row[side].get('first_receipts', [])))
        groups[category] = output
    return {'left_arm': arms[0], 'right_arm': arms[1], 'groups': groups, 'pairs': paired,
        'outcome_differences': [row for row in paired if row['outcome_equal'] is False],
        'unknown_pairs': [row for row in paired if not row['known_pair']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_bytes())
    if plan['schema_version'] != 'bounded-skills/6' or plan['training'] or plan['confirmation']:
        raise ValueError('expected registered schema6 development batch')
    kinds = {job['kind'] for job in plan['jobs']}
    if len(kinds) != 1:
        raise ValueError('do not pool different probe types')
    rows, pending = collect(args.root, plan)
    if kinds == {'d2'}:
        parent = plan['jobs'][0]['manifest']
        if ref(Path(parent['path'])) != parent:
            raise ValueError('parent D2 registration changed')
        d2 = json.loads(Path(parent['path']).read_bytes())
        d2.update(source_commit=plan['source_commit'], recovery_budget=plan['recovery_budget'])
        result = summarize(d2, [row['result'] for row in rows])
        result['recovery_budget'] = plan['recovery_budget']
    else:
        result = pair_summary(plan, rows)
    result.update(manifest=ref(args.manifest), script=ref(Path(__file__)),
        source_commit=plan['source_commit'], missing_indices=pending, complete=not pending,
        case_sources=[{'index': row['index'], 'source': row['source']} for row in rows], training=False,
        measurement_scope='closed physical records only; interrupted/startup records excluded')
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'complete': result['complete'], 'closed': len(rows), 'pending': len(pending)}))


if __name__ == '__main__':
    main()
