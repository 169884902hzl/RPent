"""Report exact state pairs, unknowns, contact stages and verifier errors."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from coordination.classify_grasp_contact_phases_20261010 import diagnose


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    d = 1+z*z/n
    c = (k/n+z*z/(2*n))/d
    h = z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/d
    return [c-h, c+h]


def metrics(rows):
    confusion = Counter()
    for row in rows:
        truth, public = row['truth_v3'], row['public']
        if truth is None:
            confusion['truth_unknown'] += 1
        elif public is None:
            confusion['public_unmeasured'] += 1
        else:
            confusion[('tp' if public else 'fn') if truth else ('fp' if public else 'tn')] += 1
    successes = sum(row['truth_v3'] is True for row in rows)
    known = sum(row['truth_v3'] is not None for row in rows)
    return {'n': len(rows), 'successes': successes, 'truth_unknown': len(rows)-known,
            'success_over_all_registered': successes/len(rows) if rows else None,
            'wilson95_over_all_registered': wilson(successes, len(rows)),
            'confusion': dict(confusion),
            'agreement_over_known_truth': (confusion['tp']+confusion['tn'])/known if known else None,
            'false_positive': confusion['fp'], 'false_negative': confusion['fn'],
            'failure_stages': dict(Counter(row['failure_stage'] for row in rows if row['truth_v3'] is not True)),
            'failure_reasons': dict(Counter(str(row['failure_reason']) for row in rows if row['truth_v3'] is not True))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--interim', action='store_true')
    args = parser.parse_args()
    registry = json.loads((args.run_root/'startup_manifest.json').read_text())
    rows, inputs, states = [], [], {}
    expected = 0
    for entry in registry:
        plan_path = Path(entry['plan']['path'])
        if pin(plan_path) != entry['plan']:
            raise ValueError('registered paired plan changed')
        plan = json.loads(plan_path.read_text())
        cases = {case['name']: case for case in plan['cases']}
        expected += len(cases)
        output = plan_path.parent.parent
        files = [output/f'job{entry["startup_job"]}/part0/probe/episodes.jsonl']
        formal_file = plan_path.parent/'formal_measurement_submission.json'
        if formal_file.exists():
            formal = json.loads(formal_file.read_text())
            files += [output/f'job{formal["formal_job"]}/part{i}/probe/episodes.jsonl' for i in range(8)]
        for path in files:
            if not path.exists():
                if args.interim:
                    continue
                raise ValueError(f'missing paired shard {path}')
            inputs.append(pin(path))
            content = path.read_bytes()
            for line, text in enumerate(content[:content.rfind(b'\n')+1].splitlines(), 1):
                raw = json.loads(text)
                case = raw['case']
                if case != cases.get(case['name']):
                    raise ValueError('physical case differs from registered state')
                first = raw.get('first_attempt') or {}
                truth = (first.get('private_hold_truth_v3') or
                         (first.get('private_setup_hold') or {}).get('truth_v3') or {}).get('success')
                receipt = first.get('receipt') or {}
                item = {'case': case['name'], 'category': entry['category'],
                        'method': 'analytic' if entry['arm']=='unified' or 'analytic' in case['condition']
                                  or 'frypan' in case['condition'] else 'pi05',
                        'state_sha256': case['state_sha256'],
                        'physical_outcome': 'success' if truth is True else 'failure' if truth is False else 'unknown'}
                phase = diagnose(raw, item)
                row = {**item, 'arm': entry['arm'], 'layout_seed': case['layout_seed'],
                       'truth_v3': truth, 'public': receipt.get('grasp_verified'),
                       'failure_stage': phase['contact_failure_class'],
                       'failure_reason': receipt.get('failure_reason'), 'contact_diagnosis': phase,
                       'status': raw['status'], 'wall_s': raw.get('wall_s'),
                       'input': inputs[-1], 'line': line, 'output_dir': raw.get('output_dir'),
                       'source_archive': plan['source_snapshot']['archive'], 'training_allowed': False}
                key = (entry['category'], case['state_sha256'])
                if entry['arm'] in states.setdefault(key, {}):
                    raise ValueError('duplicate arm/state physical outcome')
                states[key][entry['arm']] = row
                rows.append(row)
    if not args.interim and (len(registry)!=10 or expected!=1000 or len(rows)!=expected):
        raise ValueError('paired selection is incomplete')
    pairs = []
    for (category, state), arms in states.items():
        if len(arms)!=2:
            continue
        old, new = arms['locked'], arms['unified']
        a, b = old['truth_v3'], new['truth_v3']
        result = ('unknown_pair' if a is None or b is None else
                  'improved' if not a and b else 'regressed' if a and not b else
                  'both_success' if a and b else 'both_failure')
        pairs.append({'category': category, 'state_sha256': state, 'layout_seed': old['layout_seed'],
                      'result': result, 'locked': old, 'unified': new, 'training_allowed': False})
    args.output.mkdir(parents=True, exist_ok=False)
    for name, records in [('attempts', rows), ('paired_states', pairs)]:
        (args.output/(name+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in records))
    report = {'expected_attempts': 1000, 'recorded_attempts': len(rows), 'complete_pairs': len(pairs),
              'paired_changes': dict(Counter(row['result'] for row in pairs)),
              'groups': {category: {
                  arm: metrics([row for row in rows if row['category']==category and row['arm']==arm])
                  for arm in ('locked', 'unified')} | {
                  'paired_changes': dict(Counter(row['result'] for row in pairs if row['category']==category))}
                  for category in ('bottle', 'bowl', 'box', 'cup', 'frypan')},
              'overall': {arm: metrics([row for row in rows if row['arm']==arm]) for arm in ('locked','unified')},
              'artifacts': [pin(args.output/(name+'.jsonl')) for name in ('attempts','paired_states')],
              'inputs': inputs, 'producer': pin(Path(__file__)),
              'classifier': pin(Path(__file__).with_name('classify_grasp_contact_phases_20261010.py')),
              'interim': args.interim,
              'selection_only': True, 'confirmation_allowed': False, 'training_allowed': False,
              'unknowns_are_retained_in_registered_denominator': True,
              'closed_confirmation_verdicts_changed': False}
    (args.output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('inputs','groups')}, indent=2))


if __name__ == '__main__':
    main()
