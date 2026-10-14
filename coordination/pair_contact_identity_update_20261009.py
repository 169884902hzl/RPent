"""Pair completed identity/verification selections with their contact control."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load(path):
    manifest = json.loads(path.read_text())
    records = Path(manifest['records']['path'])
    if ref(records) != manifest['records']:
        raise ValueError('immutable summarized attempts changed')
    return manifest, [json.loads(line) for line in records.read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old_manifest, old = load(args.old)
    new_manifest, new = load(args.new)
    reports, pairs = {}, []
    for name, meta in new_manifest['groups'].items():
        category = name.split('/')[0]
        old_method = 'analytic_v2' if category in ('grasp_cup', 'grasp_frypan') else 'analytic'
        old_name = category + '/' + old_method
        if meta['pending'] or old_manifest['groups'][old_name]['pending']:
            reports[category] = {'status': 'waiting_complete_selection', 'recorded': meta['recorded']}
            continue
        prior = {r['state_sha256']: r for r in old
                 if r['category'] == category and r['method'] == old_method}
        current = {r['state_sha256']: r for r in new if r['category'] == category}
        if len(current) != 100 or prior.keys() != current.keys():
            raise ValueError('exactly the same 100 unique selection resets required')
        counts, reasons = Counter(), Counter()
        for state, row in current.items():
            previous = prior[state]
            a, b = previous['private_success'], row['private_success']
            known = isinstance(a, bool) and isinstance(b, bool)
            status = ('improved' if not a and b else 'regressed' if a and not b else 'same') if known else 'unknown'
            counts[status] += 1
            if status == 'regressed':
                reasons[row['physical_outcome']] += 1
            pairs.append({'category': category, 'state_sha256': state, 'transition': status,
                'old': previous, 'new': row, 'confirmation': False, 'training_allowed': False})
        flips = counts['improved'] + counts['regressed']
        pvalue = min(1., 2 * sum(math.comb(flips, i) for i in range(
            min(counts['improved'], counts['regressed']) + 1)) / 2**flips) if flips else 1.
        reports[category] = {'status': 'complete', 'paired_counts': dict(counts),
            'regression_causes': dict(reasons), 'exact_mcnemar_p_known_pairs': pvalue,
            'old_success': old_manifest['groups'][old_name]['true_successes'],
            'new_success': meta['true_successes'],
            'old_public_agreement': old_manifest['groups'][old_name]['agreement_rate'],
            'new_public_agreement': meta['agreement_rate']}
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = args.output / 'pairs.jsonl'
    ledger.write_text(''.join(json.dumps(row) + '\n' for row in pairs))
    manifest = {'sources': [ref(args.old), ref(args.new), ref(Path(__file__))],
        'records': ref(ledger), 'comparisons': reports, 'confirmation': False,
        'training_allowed': False, 'physical_replay_performed': False,
        'interpretation': 'complete selection groups only; the verification motion can affect the final physical hold'}
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': ref(path), 'comparisons': reports}))


if __name__ == '__main__':
    main()
