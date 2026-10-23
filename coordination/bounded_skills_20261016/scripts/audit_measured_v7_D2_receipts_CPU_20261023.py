"""Read recorded receipts for closed failures; do not execute or rescore physics."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read_reference(ref, *, jsonl=False):
    raw = Path(ref['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref['sha256'], ref['path']
    return [json.loads(line) for line in raw.splitlines()] if jsonl else json.loads(raw)


def trace(trial):
    receipts = []
    for row in read_reference(trial['choices'], jsonl=True):
        for receipt in row.get('receipts', []):
            receipts.append({k: receipt.get(k) for k in
                ('skill', 'outcome', 'phase', 'stop_reason', 'steps_used')})
            receipts[-1]['decision'] = row.get('index')
            receipts[-1]['failed_expectations'] = [check for check in
                receipt.get('expectation_checks', []) if check.get('passed') is False]
    failures = [r for r in receipts if r['outcome'] in ('failure', 'rejected')]
    return {'choices': trial['choices'], 'receipts': receipts,
        'failure_receipts': dict(Counter(f"{r['skill']}:{r['stop_reason']}" for r in failures)),
        'zero_step_failure_receipts': sum(r['steps_used'] == 0 for r in failures),
        'recorded_public_success_without_registered_progress':
            trial.get('private_progress_success', trial.get('success')) is False and
            any(r['stop_reason'] in ('measured_success', 'measured_success_after_handoff',
                'subtask_completed') for r in receipts),
        'scope': 'recorded public receipts; not a new physical or private-truth judgement'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    closed = args.run/'CPU_closed40'
    output = args.run/'CPU_receipt_audit_r1'
    output.mkdir(exist_ok=True)
    both = [json.loads(s) for s in (closed/'both_failed_subtasks.jsonl').read_text().splitlines()]
    comparisons = [json.loads(s) for s in (closed/'comparison.jsonl').read_text().splitlines()]
    annotated = []
    for detail in both:
        item = {'case': detail['case'], 'subtask': detail['subtask'], 'trials': []}
        for trial in detail['trials']:
            item['trials'].append({**trial, 'recorded_receipt_trace': trace(trial)})
        annotated.append(item)
    gaps = []
    for row in comparisons:
        if row['sampled_envelope_success'] is not True or row['success']:
            continue
        raw = read_reference(row['summary'])
        trials = []
        for trial in raw.get('full_replay', []):
            trials.append({**{k: trial.get(k) for k in ('subtask', 'method', 'trial_seed',
                'initial_physics_sha256', 'success', 'private_progress_success',
                'native_task_success', 'reason', 'sim_steps', 'source_public_id',
                'target_public_id', 'executed_vla_variants')},
                'recorded_receipt_trace': trace(trial)})
        gaps.append({'case': row['case'], 'summary': row['summary'], 'full_replay': trials})
    for name, values in (('both_failed_receipts.jsonl', annotated), ('replay_gap_receipts.jsonl', gaps)):
        (output/name).write_text(''.join(json.dumps(v, sort_keys=True)+'\n' for v in values))
    manifest = {'both_failed_subtasks': len(annotated), 'trials': sum(len(v['trials']) for v in annotated),
        'replay_gap_cases': len(gaps), 'evaluation_only': True, 'training': False,
        'scope': 'CPU receipt extraction; original scores and all physical records unchanged',
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.jsonl')}}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
