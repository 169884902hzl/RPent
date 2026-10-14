"""Compare planned cup contacts with saved public measurements, never private poses."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records, inputs, cached = [], [], {}
    for report in args.report:
        rows_path = report / 'rows.jsonl'
        inputs.append(pin(rows_path))
        for row in map(json.loads, rows_path.open()):
            if row['type'] != 'grasp_cup':
                continue
            path = Path(row['input'])
            if path not in cached:
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != row['input_sha256']:
                    raise ValueError('closed physical ledger changed')
                cached[path] = data.splitlines()
            raw = json.loads(cached[path][row['line'] - 1])
            first = raw.get('first_attempt') or {}
            receipt = first.get('receipt') or {}
            plan = receipt.get('analytic_grasp_plan') or {}
            initial = next((e for e in (first.get('public_before') or {}).get('entities', [])
                            if e['id'] == receipt.get('object')), None)
            planned, measured = plan.get('xyz'), plan.get('measured_entity_xyz')
            records.append({'group': row['group'], 'case': row['case'], 'state_sha256': row['state_sha256'],
                'registered_v3': row['registered_v3'],
                'initial_public_entity': initial, 'plan': plan,
                'contact_to_initial_public_centre_m': math.dist(planned, initial['xyz'])
                    if planned and initial else None,
                'contact_to_planning_measurement_centre_m': math.dist(planned, measured)
                    if planned and measured else None,
                'failure_reason': row['failure_reason'],
                'physical_input': {'path': str(path), 'sha256': row['input_sha256'], 'line': row['line']},
                'private_coordinates_used': False})
    groups = {}
    for group in sorted({r['group'] for r in records}):
        rows = [r for r in records if r['group'] == group]
        item = {'registered_n': len(rows)}
        for key in ('contact_to_initial_public_centre_m', 'contact_to_planning_measurement_centre_m'):
            values = [r[key] for r in rows if r[key] is not None]
            item[key] = {'measured_n': len(values), 'missing_n': len(rows) - len(values),
                'median_p90_max_m': np.quantile(values, [.5, .9, 1]).tolist() if values else None,
                'over_10cm_n': sum(v > .10 for v in values)}
            failed_values = [r[key] for r in rows if r['registered_v3'] is False and r[key] is not None]
            item[key]['v3_failure_only'] = {
                'registered_failure_n': sum(r['registered_v3'] is False for r in rows),
                'measured_n': len(failed_values),
                'median_p90_max_m': np.quantile(failed_values, [.5, .9, 1]).tolist() if failed_values else None,
                'over_10cm_n': sum(v > .10 for v in failed_values)}
        groups[group] = item
    args.output.mkdir(parents=True, exist_ok=False)
    rows_path = args.output / 'rows.jsonl'
    rows_path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    producer = args.output / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    (args.output / 'manifest.json').write_text(json.dumps({'groups': groups, 'inputs': inputs,
        'producer': pin(producer), 'records': pin(rows_path), 'private_coordinates_used': False,
        'limits': ['Intentional rim/handle offsets are not identity errors by themselves.',
                   'The initial observation and precontact measurement can occur at different physical steps.'],
        'training_allowed': False}, indent=2) + '\n')
    print(json.dumps(groups))


if __name__ == '__main__':
    main()
