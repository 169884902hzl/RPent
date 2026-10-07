"""Read only the eight named moka smoke ledgers and preserve first outcomes."""

import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def on_success(row):
    status = row.get('private_original_task_status_after') or {}
    targets = {tuple(g) for g in row['case'].get('private_original_goal_predicates', [])
               if len(g) == 3 and g[0].lower() == 'on' and 'moka' in g[1]}
    flags = [value for goal, value in zip(status.get('goals', []), status.get('satisfied', []))
             if tuple(goal) in targets]
    return flags[0] if len(flags) == 1 and isinstance(flags[0], bool) else None


def bounded(successes, known, n):
    return {'successes': successes, 'known': known, 'unknown_or_pending': n-known,
            'denominator': n, 'worst_case_rate': successes/n,
            'best_case_rate': (successes+n-known)/n,
            'known_rate': successes/known if known else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    manifest = base / 'preparation/moka_original_public_placement_visited10.json'
    plan = json.loads(manifest.read_text())
    invocations, inputs, missing, partial_lines = [], [], [], []
    for part in range(8):
        path = base / f'smoke10/job{args.job}/part{part}/probe/episodes.jsonl'
        if not path.exists():
            missing.append(str(path))
            continue
        inputs.append(identity(path))
        for line_index, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                partial_lines.append({'path': str(path), 'line': line_index})
                continue
            row['source'] = {'path': str(path), 'line': line_index}
            invocations.append(row)
    first, nonphysical = {}, []
    for row in invocations:
        name = row['case']['name']
        receipt = row.get('first_receipt') or row.get('public_receipt_before_private_metrology') or {}
        physical = bool(row.get('physical_execution_observed') or row.get('executed_vla_actions')
                        or row.get('executed_public_motion_actions') or receipt.get('executed'))
        if physical:
            first.setdefault(name, row)
        else:
            nonphysical.append(row)
    cases, confusion = [], {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
    success, known, agreement, paired = 0, 0, 0, 0
    for case in plan['cases']:
        row = first.get(case['name'])
        if row is None:
            cases.append({'case': case['name'], 'episode': case['episode'],
                          'state_sha256': case['state_sha256'], 'first_physical': False})
            continue
        if row['case']['state_sha256'] != case['state_sha256']:
            raise ValueError('Physical receipt state differs from manifest')
        truth = on_success(row)
        receipt = row.get('first_receipt') or row.get('public_receipt_before_private_metrology') or {}
        verdict = receipt.get('place_verified')
        if not isinstance(verdict, bool):
            verdict = None
        known += truth is not None
        success += truth is True
        if truth is not None and verdict is not None:
            paired += 1
            agreement += truth == verdict
            confusion[('TP' if truth else 'FP') if verdict else ('FN' if truth else 'TN')] += 1
        cases.append({'case': case['name'], 'episode': case['episode'],
            'state_sha256': case['state_sha256'], 'first_physical': True,
            'official_moka_On_success': truth, 'public_place_verified': verdict,
            'official_original_task_done': (row.get('private_original_task_status_after') or {}).get('done'),
            'source': row['source'], 'receipt': receipt,
            'public_placement_measurements': row.get('public_placement_measurements'),
            'chunks': row.get('chunks'), 'executed_vla_actions': row.get('executed_vla_actions'),
            'result': row.get('result'), 'raised_error': row.get('raised_error'),
            'infrastructure_failure': row.get('infrastructure_failure'),
            'case_had_infrastructure_failure': row.get('case_had_infrastructure_failure')})
    n = len(plan['cases'])
    report = {'scope': 'Ten previously selected original states, new public-placement development smoke',
        'job': args.job, 'manifest': identity(manifest), 'source_snapshot': plan['source_snapshot'],
        'producer': identity(Path(__file__).resolve()), 'ledger_inputs': inputs,
        'missing_named_ledgers': missing, 'partial_json_lines': partial_lines,
        'registered': n, 'first_physical': len(first), 'observed_invocations': len(invocations),
        'nonphysical_development_invocations': len(nonphysical),
        'physical_success': bounded(success, known, n),
        'public_placement_agreement': bounded(agreement, paired, n), 'confusion': confusion,
        'cases': cases, 'qualification_authorized': False, 'new_training_rows': 0,
        'first_attempt_policy': 'Retain first actual physical result; no replacement labels or physical reruns',
        'confirmation_state_count': 0, 'confirm_100_threshold_satisfied': False}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'nonphysical_invocations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in nonphysical))
    print(json.dumps({k: report[k] for k in ('job', 'registered', 'first_physical', 'observed_invocations',
        'physical_success', 'public_placement_agreement', 'confusion', 'nonphysical_development_invocations')}))


if __name__ == '__main__':
    main()
