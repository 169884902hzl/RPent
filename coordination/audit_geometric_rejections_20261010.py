"""Count candidate rejection and locked private failure evidence by method."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cache, groups, records = {}, defaultdict(list), []
    for row in map(json.loads, (args.report / 'rows.jsonl').open()):
        path = Path(row['input'])
        if path not in cache:
            if pin(path)['sha256'] != row['input_sha256']:
                raise ValueError('closed physical evidence changed')
            cache[path] = [json.loads(line) for line in path.open()]
        raw = cache[path][row['line']-1]
        first = raw.get('first_attempt') or {}
        receipt = first.get('receipt') or {}
        rankings = receipt.get('geometric_grasp_rankings') or []
        candidates = rankings[-1]['candidates'] if rankings else []
        collisions = Counter()
        for candidate in candidates:
            for collision in candidate.get('collision', []):
                for scope in ('scene', 'target'):
                    for part, n in collision.get(scope, {}).items():
                        if n:
                            collisions[scope + '/' + part] += 1
        checks = (first.get('private_hold_truth_v3') or {}).get('checks') or []
        predicates = Counter()
        for check in checks:
            if check.get('qualifies') is not False:
                continue
            if check.get('clearance_m', .03) < .03:
                predicates['whole_object_lift_below_3cm'] += 1
            if check.get('dual_finger_contact') is False:
                predicates['missing_two_finger_contact'] += 1
            if check.get('relative_com_displacement_m', 0) > .01:
                predicates['relative_tcp_slip_over_1cm'] += 1
            if check.get('counterfactual_load_bearing_support') is True:
                predicates['external_load_bearing_support'] += 1
        item = {'case': row['case'], 'group': row['group'],
            'state_sha256': row['state_sha256'], 'registered_v3': row['registered_v3'],
            'failure_reason': row['failure_reason'], 'candidate_n': len(candidates),
            'accepted_n': sum(not c['rejected'] for c in candidates),
            'candidate_rejections': dict(Counter(reason for c in candidates for reason in c['rejected'])),
            'candidate_collision_scopes': dict(collisions),
            'private_failed_predicate_frames_diagnostic_only': dict(predicates),
            'private_unknown_reasons': sorted({c['unknown_reason'] for c in checks if c.get('unknown_reason')}),
            'physical_input': {**pin(path), 'line': row['line']}, 'training_allowed': False}
        records.append(item)
        groups[row['group']].append(item)
    args.output.mkdir(parents=True, exist_ok=False)
    records_path = args.output / 'rows.jsonl'
    records_path.write_text(''.join(json.dumps(row) + '\n' for row in records))
    summaries = {}
    for group, items in groups.items():
        summaries[group] = {'n': len(items),
            'candidate_n': sum(r['candidate_n'] for r in items),
            'accepted_candidate_n': sum(r['accepted_n'] for r in items),
            'cases_with_rankings_but_no_accepted': sum(r['candidate_n'] > 0 and not r['accepted_n'] for r in items),
            'candidate_rejections': dict(sum((Counter(r['candidate_rejections']) for r in items), Counter())),
            'candidate_collision_scopes': dict(sum((Counter(r['candidate_collision_scopes']) for r in items), Counter())),
            'private_failed_predicate_cases_diagnostic_only': dict(Counter(
                reason for r in items if r['registered_v3'] is False
                for reason in r['private_failed_predicate_frames_diagnostic_only'])),
            'private_unknown_cases': dict(Counter(reason for r in items for reason in r['private_unknown_reasons']))}
    manifest = {'producer': pin(Path(__file__)), 'input': pin(args.report / 'rows.jsonl'),
        'records': pin(records_path), 'groups': summaries,
        'private_evidence_usage': 'diagnosis only; never supplied to sampling, ranking or public verification',
        'qualification_allowed': False, 'training_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(summaries))


if __name__ == '__main__':
    main()
