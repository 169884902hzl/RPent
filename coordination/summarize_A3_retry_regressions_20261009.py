"""Separate direct masked successful retries from unidentifiable path effects."""

import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    diagnoses = [json.loads(line) for line in args.input.read_text().splitlines()]
    records = []
    for row in diagnoses:
        if not row['regression']:
            continue
        old = row['baseline']['macro_attempts']
        if not old:
            direct = 'baseline_success_used_no_vla_task'
        elif old[0]['official_success'] is True:
            direct = 'baseline_first_vla_task_succeeded_no_failed_retry'
        elif all(e['official_success'] is False for e in old):
            direct = 'no_baseline_vla_task_attempt_succeeded'
        else:
            direct = 'successful_baseline_retry_requires_matched_prefix_test'
        records.append({'episode': row['episode'], 'current_skill_sim_steps': row['current']['skill_steps'],
            'baseline_macro_attempts': old, 'current_macro_attempts': row['current']['macro_attempts'],
            'direct_retry_evidence': direct,
            'indirect_causality': 'not identifiable: policies reached different states and chose different actions',
            'source_choices': [row['baseline']['choices'], row['current']['choices']],
            'training_allowed': False})
    if len(records) != 7:
        raise ValueError('expected all seven retained regression episodes')
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / 'regressions.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    table = ['Seven paired development regressions; total 49/80 to 45/80, improved3/regressed7, exact p=0.34375.',
        'No efficacy conclusion follows from these 80 pairs.', '',
        '| suite/task/init | current steps by skill | direct retry evidence |', '|---|---|---|']
    for row in records:
        e = row['episode']
        table.append(f"| {e['suite']}/{e['task']}/{e['seed']} | "
            + ', '.join(f'{k}:{v}' for k, v in sorted(row['current_skill_sim_steps'].items()))
            + f" | {row['direct_retry_evidence']} |")
    table.extend(['', 'All seven lack a direct recorded failed-vla_task-then-successful-vla_task retry in the baseline.',
                  'This excludes that particular recorded explanation; it does not rule out indirect path effects.'])
    (args.output / 'REPORT.md').write_text('\n'.join(table) + '\n')
    manifest = {'registered': 7, 'recorded': 7, 'records': ref(path),
        'inputs': [ref(args.input), ref(Path(__file__))], 'confirmation': False, 'training_allowed': False,
        'matched_prefix_physical_replay': False, 'source': 'retained pre-execution choices and measured runtime receipts'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': ref(args.output / 'manifest.json'), 'recorded': 7}))


if __name__ == '__main__':
    main()
