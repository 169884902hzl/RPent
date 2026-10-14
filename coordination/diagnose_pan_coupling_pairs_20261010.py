"""Inspect paired pan regressions without changing any recorded verdict."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PAIR = ROOT / 'coordination/geometric_methods_event_closed_20261010_r1/geometric_grasp_selection_20261010_r13__frypan_public_coupling__vs_parent/rows.jsonl'
OUT = ROOT / 'coordination/pan_public_coupling_regressions_20261010_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load(path, expected, line):
    path = ROOT / path
    if pin(path)['sha256'] != expected:
        raise ValueError('paired physical ledger changed')
    with path.open() as stream:
        for index, text in enumerate(stream, 1):
            if index == line:
                return json.loads(text)
    raise ValueError('paired physical record absent')


def evidence(raw):
    first = raw.get('first_attempt') or {}
    receipt = first.get('receipt') or {}
    truth = first.get('private_hold_truth_v3') or {}
    failed = Counter()
    for check in truth.get('checks', []):
        if check.get('dual_finger_contact') is False:
            failed['dual_finger_contact_missing'] += 1
        if check.get('clearance_m') is not None and check['clearance_m'] < truth['required_clearance_m']:
            failed['support_clearance_missing'] += 1
        if check.get('relative_com_displacement_m') is not None and check['relative_com_displacement_m'] > truth['required_relative_displacement_m']:
            failed['relative_motion_over_1cm'] += 1
        if check.get('counterfactual_load_bearing_support'):
            failed['non_gripper_support'] += 1
    plan = receipt.get('analytic_grasp_plan') or {}
    return {'failure_reason': receipt.get('failure_reason'),
            'closed': bool(receipt.get('analytic_close')),
            'public': receipt.get('grasp_verified'), 'v3': truth.get('success'),
            'final_window_failed_samples': dict(failed),
            'public_planned_xyz': plan.get('xyz'), 'public_planned_yaw': plan.get('yaw'),
            'handle_geometry': plan.get('handle_geometry'),
            'sim_steps': receipt.get('sim_steps_used')}


def main():
    rows, classes = [], Counter()
    for row in map(json.loads, PAIR.open()):
        if row['v3_transition'] != 'regressed':
            continue
        before = row['before_input']
        left = evidence(load(before['path'], before['sha256'], before['line']))
        right = evidence(load(row['input'], row['input_sha256'], row['line']))
        reason = right['failure_reason'] if not right['closed'] else 'closed_but_registered_hold_failed'
        classes[reason] += 1
        rows.append({'case': row['case'], 'state_sha256': row['state_sha256'],
                     'before_input': before, 'after_input': {'path': row['input'],
                     'sha256': row['input_sha256'], 'line': row['line']},
                     'before': left, 'after': right, 'stage_class': reason})
    OUT.mkdir(exist_ok=False)
    records = OUT / 'records.jsonl'
    records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    manifest = {'input': pin(PAIR), 'producer': pin(Path(__file__)),
                'records': pin(records), 'regressions': len(rows),
                'failure_stage_classes': dict(classes), 'private_diagnostic_only': True,
                'training_allowed': False,
                'limits': ['New active verification is part of the physical method.',
                           'A regression before closure cannot be attributed to the later lift probe.',
                           'Same-source control paths do not guarantee identical RGB-D segmentation.']}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
