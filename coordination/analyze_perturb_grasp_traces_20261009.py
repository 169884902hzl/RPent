"""Separate pre-contact motion misses, contact failures and verifier errors."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from robots.libero.v5_motion_classification import classify_move
from scripts.summarize_v5_skill501_original import infrastructure_result


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def analyze(row):
    stage = row.get('first_attempt') or {}
    receipt = stage.get('receipt') or {}
    truth = stage.get('private_hold_truth_v2', {}).get('success')
    public = receipt.get('grasp_verified')
    motions = stage.get('motion_evidence') or []
    contacts = [m for m in motions if m.get('name') == 'vla_act_chunk']
    before = stage.get('public_before') or {}
    entity = next((e for e in before.get('entities', []) if e['id'] == receipt.get('object')), None)
    policy_pose = [m['final_eef_pos'] for m in contacts if m.get('final_eef_pos')]
    deepest = min(policy_pose, key=lambda xyz: xyz[2]) if policy_pose else None
    deepest_xy_distance = (math.dist(deepest[:2], entity['xyz'][:2])
                           if deepest and entity else None)
    reason = receipt.get('failure_reason')
    if not stage:
        category = 'binding_or_precondition_failure'
    elif reason in ('approach_not_reached', 'waypoint_not_reached') and not contacts:
        category = 'scripted_motion_failed_before_contact'
    elif truth is True and public is not True:
        category = 'true_hold_not_verified'
    elif truth is False and public is True:
        category = 'false_verified_hold'
    elif truth is True:
        category = 'true_hold_verified'
    elif truth is False and contacts:
        category = 'contact_executed_no_sustained_hold'
    elif truth is False:
        category = 'no_sustained_hold_without_contact_trace'
    else:
        category = 'private_hold_unknown'
    choice = {'decision': 0, 'selected': stage.get('selected'), 'receipt': receipt,
              'measurements': before.get('entities', []), 'motion_evidence': motions}
    classifications = []
    for motion in motions:
        if motion.get('name') != 'move_to' or motion.get('final_dist_m', 0) <= .02:
            continue
        if motion.get('last_10_steps') and motion.get('final_contact_and_joints') is not None:
            classifications.append(classify_move(motion, choice))
        else:
            classifications.append({'classification': 'insufficient_motion_trace',
                'final_dist_m': motion.get('final_dist_m'), 'steps_used': motion.get('steps_used')})
    return {'case': row['case']['name'], 'state_sha256': row['case']['state_sha256'],
        'object_category': row['case']['type'], 'method': row['case']['condition'],
        'classification': category, 'failure_reason': reason, 'private_truth': truth,
        'public_verified': public, 'contact_chunks': len(contacts),
        'contact_sim_steps': sum(m.get('steps_used', 0) for m in contacts),
        'total_sim_steps': receipt.get('sim_steps_used'),
        'current_public_object': entity, 'deepest_contact_eef_xyz': deepest,
        'deepest_contact_xy_distance_to_measured_object_m': deepest_xy_distance,
        'scripted_motion_classifications': classifications,
        'source': row['output_dir'], 'private_diagnostic_only': True, 'training_allowed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registered, records, references, infrastructure = {}, {}, [], []
    for root in args.root:
        for p in root.glob('*/preparation/selection.json'):
            plan = json.loads(p.read_text())
            if plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']:
                raise ValueError('only registered original-only selection is accepted')
            references.append(ref(p))
            for case in plan['cases']:
                if case['kind'] == 'grasp':
                    if case['name'] in registered:
                        raise ValueError('duplicate registered grasp')
                    registered[case['name']] = case
        for p in root.rglob('episodes.jsonl'):
            data = p.read_bytes(); boundary = data.rfind(b'\n') + 1
            references.append(ref(p))
            for line in data[:boundary].splitlines():
                row = json.loads(line); case = row['case']
                if case['kind'] != 'grasp':
                    continue
                if case != registered.get(case['name']):
                    raise ValueError('unregistered or changed physical case')
                if infrastructure_result(row):
                    infrastructure.append({'case': case['name'], 'source': ref(p), 'status': row['status']})
                    continue
                if case['name'] in records:
                    raise ValueError('duplicate physical result')
                records[case['name']] = analyze(row)
    grouped, motions = defaultdict(Counter), Counter()
    for row in records.values():
        grouped[row['object_category']+'/'+row['method']][row['classification']] += 1
        motions.update(m['classification'] for m in row['scripted_motion_classifications'])
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = args.output / 'grasp_attempt_diagnoses.jsonl'
    ledger.write_text(''.join(json.dumps(row)+'\n' for row in records.values()))
    manifest = {'registered': len(registered), 'completed': len(records),
        'pending': len(registered)-len(records), 'by_category_and_method': dict(grouped),
        'scripted_motion_classes_over2cm': dict(motions), 'infrastructure_attempts': infrastructure,
        'records': ref(ledger), 'inputs': references, 'source': ref(Path(__file__)),
        'limitations': ['Contact at a different position does not prove policy memorization.',
                       'Private contact or joint evidence does not prove a causal collision or IK defect.',
                       'A residual over2cm may be inside the configured approach acceptance.'],
        'selection_only': True, 'behavior_frozen': False, 'training_allowed': False}
    p = args.output / 'manifest.json'; p.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'manifest': ref(p), 'completed': len(records),
                      'by_category_and_method': dict(grouped)}))


if __name__ == '__main__':
    main()
