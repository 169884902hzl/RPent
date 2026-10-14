"""Expose closed public-hold methods to the same-state geometry comparison."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary', type=Path, action='append', default=[])
    args = parser.parse_args()
    rows, groups, plans, inputs = [], {}, [], []
    summaries = [ROOT / 'coordination' / (name + '_physical_hold_r18_closed_20261010') / 'summary.json'
                 for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
    for summary_path in dict.fromkeys([*summaries, *args.summary]):
        rows_path = summary_path.parent / 'rows.jsonl'
        summary = json.loads(summary_path.read_text())
        if not summary['complete'] or summary['recorded_n'] != summary['registered_n']:
            raise ValueError('method is not closed')
        plan_path = Path(summary['plan']['path'])
        if pin(plan_path) != summary['plan']:
            raise ValueError('method registration changed')
        name = plan_path.parent.parent.name
        group = plan_path.parent.parent.parent.name + '/' + name
        method_rows = list(map(json.loads, rows_path.open()))
        if len(method_rows) != summary['registered_n']:
            raise ValueError('all registered cases must be retained')
        for row in method_rows:
            path = Path(row['input'])
            if not path.is_absolute():
                path = ROOT / path
            rows.append({**row, 'group': group, 'input': str(path),
                         'public': row['public'], 'registered_v3': row['registered_v3']})
        groups[group] = {'registered_n': summary['registered_n'], 'pending_n': 0,
                         'recorded_n': len(method_rows)}
        plans.append(summary['plan'])
        inputs.append({'summary': pin(summary_path), 'rows': pin(rows_path)})
    args.output.mkdir(parents=True, exist_ok=False)
    producer = args.output / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    records = args.output / 'rows.jsonl'
    records.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (args.output / 'manifest.json').write_text(json.dumps({'groups': groups, 'plans': plans,
        'inputs': inputs, 'producer': pin(producer), 'records': pin(records),
        'physical_or_verifier_labels_changed': False, 'training_allowed': False,
        'purpose': 'one whole source per method; never combine another executor with this verifier'}, indent=2) + '\n')
    print(json.dumps({'methods': len(groups), 'records': len(rows)}))


if __name__ == '__main__':
    main()
