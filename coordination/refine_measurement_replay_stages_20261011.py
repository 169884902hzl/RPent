"""Classify new development traces without changing closed confirmation labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from coordination.classify_grasp_contact_phases_20261010 import diagnose


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def current_stage(raw, pair):
    new = pair['new']
    first = raw.get('first_attempt') or {}
    receipt = first.get('receipt') or {}
    truth = (first.get('private_hold_truth_v3') or
             (first.get('private_setup_hold') or {}).get('truth_v3') or {})
    physical = new['physically_executed']
    item = {'case': pair['case'], 'category': pair['category'],
            'method': 'analytic' if 'analytic' in raw['case']['condition']
                      or 'frypan' in raw['case']['condition'] else 'pi05',
            'state_sha256': pair['state_sha256'],
            'physical_outcome': 'success' if truth.get('success') is True else
                                'failure' if truth.get('success') is False else 'unknown'}
    result = diagnose(raw, item)
    original_stage = result['contact_failure_class']
    if not physical:
        stage = ('preexecution_source_binding_missing'
                 if raw['status'] == 'first_attempt_public_binding_missing' else
                 'preexecution_geometry_rejected:' + str(receipt.get('failure_reason')))
    elif truth.get('success') is True:
        stage = 'development_end_success'
    elif original_stage == 'lift_observed_but_end_failure_reason_unresolved':
        failures = result['registered_final_window_failure_samples']
        reasons = [name for name in (
            'whole_object_not_clear_of_original_support',
            'dual_finger_contact_missing', 'object_moves_relative_to_gripper',
            'supported_by_non_gripper_geometry') if failures.get(name)]
        if not reasons:
            raise ValueError('lift end failure lacks registered truth evidence')
        stage = 'lift_then_final_window_failed:' + '+'.join(reasons)
    else:
        stage = original_stage
    return {**pair, 'refined_development_stage': stage,
            'development_contact_diagnosis': result,
            'classification_uses_current_development_outcome': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pairs = [json.loads(line) for line in args.input.read_text().splitlines()]
    cache, records = {}, []
    for pair in pairs:
        source = pair['new']['input']
        path = Path(source['path'])
        if path not in cache:
            if pin(path) != source:
                raise ValueError('development source ledger changed')
            cache[path] = [json.loads(line) for line in path.read_text().splitlines()]
        raw = cache[path][pair['new']['line']-1]
        if raw['case']['name'] != pair['case']:
            raise ValueError('development case identity mismatch')
        records.append(current_stage(raw, pair))
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output/'paired_rows.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    physical = [row for row in records if row['new']['physically_executed']]
    report = {
        'input': pin(args.input), 'producer': pin(Path(__file__)), 'paired_rows': pin(path),
        'classifier': pin(Path(__file__).with_name('classify_grasp_contact_phases_20261010.py')),
        'registered_states': len(records), 'actually_executed_skills': len(physical),
        'complete_executed_control_traces': sum(row['new']['complete_control_trace'] for row in physical),
        'whole_skill_trace_not_saved': sum(row['refined_development_stage']=='whole_skill_trace_not_saved'
                                           for row in records),
        'unclassified_stage': sum('unresolved' in row['refined_development_stage'] for row in records),
        'no_physical_attempts': [{key: row[key] for key in (
            'case', 'category', 'layout_seed', 'state_sha256', 'refined_development_stage', 'new')}
            for row in records if not row['new']['physically_executed']],
        'per_category': {group: {
            'registered': sum(row['category']==group for row in records),
            'executed': sum(row['category']==group for row in physical),
            'development_stages': dict(Counter(row['refined_development_stage']
                                              for row in records if row['category']==group))}
            for group in ('bottle', 'bowl', 'box', 'cup', 'frypan')},
        'old_pan16': {'n': sum(row['category']=='frypan' and row['old']['v3'] is None for row in records),
                     'new_truth_unknown': sum(row['new']['v3_diagnostic_only'] is None for row in records
                                              if row['category']=='frypan' and row['old']['v3'] is None)},
        'closed_verdicts_changed': False, 'training_allowed': False,
        'development_only': True, 'qualification_claim': False,
        'stage_limitations': 'Saved contact observations identify phases; they alone do not prove collision causality.'}
    (args.output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k!='no_physical_attempts'}, indent=2))


if __name__ == '__main__':
    main()
