"""Pair completed method selections by category and immutable reset bytes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    attempts = Path(manifest['records']['path'])
    if ref(attempts) != manifest['records']:
        raise ValueError('selection attempts changed')
    groups = defaultdict(dict)
    for line in attempts.read_text().splitlines():
        row = json.loads(line)
        key = (row['category'], row['method'])
        state = row['state_sha256']
        if state in groups[key]:
            raise ValueError('method contains a repeated reset')
        groups[key][state] = row
    report, pairs = {}, []
    for (category, method), current in groups.items():
        if method == 'pi05':
            continue
        baseline = groups.get((category, 'pi05'), {})
        meta = manifest['groups'][category + '/' + method]
        base_meta = manifest['groups'].get(category + '/pi05', {})
        if meta['pending'] or base_meta.get('pending', 100):
            report[category + '/' + method] = {
                'status': 'pending_complete_selection',
                'current_recorded': len(current), 'baseline_recorded': len(baseline)}
            continue
        if len(current) != 100 or current.keys() != baseline.keys():
            raise ValueError('completed methods do not have the same 100 resets')
        matrix, unknown = Counter(), 0
        for state, new in current.items():
            old = baseline[state]
            a, b = old['private_success'], new['private_success']
            known = isinstance(a, bool) and isinstance(b, bool)
            if known:
                matrix[f'old{int(a)}_new{int(b)}'] += 1
            else:
                unknown += 1
            pairs.append({'category': category, 'method': method,
                'state_sha256': state, 'pi05': old, 'current': new,
                'both_truth_known': known, 'confirmation': False, 'training_allowed': False})
        good, bad = matrix['old0_new1'], matrix['old1_new0']
        flips = good + bad
        pvalue = min(1., 2 * sum(math.comb(flips, i)
            for i in range(min(good, bad) + 1)) / 2**flips) if flips else 1.
        report[category + '/' + method] = {
            'status': 'complete', 'registered_pairs': 100,
            'known_truth_pairs': sum(matrix.values()), 'unknown_truth_pairs': unknown,
            'paired_counts': dict(matrix), 'improved': good, 'regressed': bad,
            'exact_mcnemar_p_known_truth_pairs': pvalue,
            'interpretation': 'method-selection data only; not held-out qualification'}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'paired.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in pairs))
    result = {'input_manifest': ref(args.manifest), 'input_attempts': ref(attempts),
        'script': ref(Path(__file__)), 'pairs': ref(path), 'comparisons': report,
        'confirmation': False, 'training_allowed': False}
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'manifest': ref(path), 'comparisons': report}))


if __name__ == '__main__':
    main()
