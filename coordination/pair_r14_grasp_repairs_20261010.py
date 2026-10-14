"""Same-state paired repair summaries, retaining unknowns and original labels."""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
from pathlib import Path

from coordination.summarize_registered_grasp_v3r9 import metric, confusion


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--method', action='append', help='summarize only these method directory names')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    baseline = {r['case']: r for r in map(json.loads, args.baseline.open())}
    args.output.mkdir(parents=True, exist_ok=False)
    closed = args.output / 'closed_ledgers'
    closed.mkdir()
    records, plans, inputs, infra, registered = [], [], [], [], {}
    for root in args.root:
        for parent in sorted(root.iterdir()):
            if args.method and parent.name not in args.method:
                continue
            plan_path = parent / 'preparation/selection.json'
            if not plan_path.is_file() or (parent / 'preparation/superseded_submission.json').exists():
                continue
            plan = json.loads(plan_path.read_text())
            if plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']:
                raise ValueError('only locked original-layout selection plans accepted')
            plans.append(pin(plan_path))
            name = root.name + '/' + parent.name
            registered[name] = len(plan['cases'])
            cases = {c['name']: c for c in plan['cases']}
            seen = set()
            for path in sorted(parent.glob('job*/part*/probe/episodes.jsonl')):
                data = path.read_bytes(); data = data[:data.rfind(b'\n') + 1]
                output = closed / (hashlib.sha256(str(path).encode()).hexdigest()[:20] + '.jsonl')
                output.write_bytes(data)
                closed_pin = pin(output)
                inputs.append({'source': str(path), 'closed_prefix': closed_pin})
                for line_no, line in enumerate(data.splitlines(), 1):
                    raw = json.loads(line); case = raw['case']
                    if case != cases[case['name']]:
                        raise ValueError('case changed from registered plan')
                    if raw.get('infrastructure_failure'):
                        infra.append({'case': case['name'], 'input': str(output), 'line': line_no})
                        continue
                    if case['name'] in seen:
                        raise ValueError('duplicate physical trial')
                    seen.add(case['name'])
                    old = baseline[case['paired_baseline_case']]
                    if old['state_sha256'] != case['state_sha256']:
                        raise ValueError('paired state bytes differ')
                    first = raw.get('first_attempt') or {}; receipt = first.get('receipt') or {}
                    reason = receipt.get('failure_reason') or raw.get('binding_error')
                    old_descend = old['failure_reason'] == 'analytic_descend_not_reached'
                    new_descend = reason == 'analytic_descend_not_reached'
                    records.append({'group': name, 'case': case['name'], 'baseline_case': old['case'],
                        'type': case['type'], 'layout_seed': case['layout_seed'],
                        'state_sha256': case['state_sha256'], 'input': str(output),
                        'input_sha256': closed_pin['sha256'], 'line': line_no,
                        'baseline_failure_reason': old['failure_reason'], 'failure_reason': reason,
                        'baseline_descend_failure': old_descend, 'descend_failure': new_descend,
                        'baseline_exclusive_v2': old['private_success'],
                        'exclusive_v2': (first.get('private_hold_truth_v2') or {}).get('success'),
                        'registered_v3': (first.get('private_hold_truth_v3') or {}).get('success'),
                        'public': receipt.get('grasp_verified'), 'baseline_public': old['public_verified'],
                        'sim_steps': receipt.get('sim_steps_used'), 'status': raw['status'],
                        'maximum_ranked_candidates': max((len(e['candidates']) for e in
                            receipt.get('geometric_grasp_rankings', [])), default=0),
                        'new_plan': receipt.get('analytic_grasp_plan'), 'training_allowed': False})
    groups = defaultdict(list)
    for r in records:
        groups[r['group']].append(r)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'baseline': pin(args.baseline), 'plans': plans, 'inputs': inputs,
        'producer': pin(Path(__file__)), 'infrastructure_attempts': infra,
        'groups': {g: {'registered_n': n, 'recorded_n': len(groups[g]), 'pending_n': n-len(groups[g]),
            'descend_before_on_matched_states': sum(r['baseline_descend_failure'] for r in groups[g]),
            'descend_after_on_matched_states': sum(r['descend_failure'] for r in groups[g]),
            'descend_resolved': sum(r['baseline_descend_failure'] and not r['descend_failure'] for r in groups[g]),
            'descend_new': sum(not r['baseline_descend_failure'] and r['descend_failure'] for r in groups[g]),
            'v3_success_observed_denominator': metric(sum(r['registered_v3'] is True for r in groups[g]), len(groups[g])),
            'v3_truth_unknown': sum(r['registered_v3'] is None for r in groups[g]),
            'v3_public_verifier': confusion(groups[g], 'registered_v3'),
            'old_exclusive_v2_before': dict(Counter(str(r['baseline_exclusive_v2']) for r in groups[g])),
            'old_exclusive_v2_after': dict(Counter(str(r['exclusive_v2']) for r in groups[g])),
            'failure_reasons': dict(Counter(r['failure_reason'] for r in groups[g]))}
            for g, n in registered.items()},
        'limits': ['Old exclusive-v2 and registered-v3 labels are separate axes.',
                  'All partial results are selection evidence; no independent confirmation claimed.'],
        'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('plans', 'inputs')}, indent=2))


if __name__ == '__main__':
    main()
