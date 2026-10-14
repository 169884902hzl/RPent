"""Retain scored labels while separating support contacts from missed grasps."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--truth-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    truth_source = ref(args.truth_source)
    manifest = json.loads(args.replay.read_text())
    pairs_path = Path(manifest['records']['path'])
    if ref(pairs_path) != manifest['records']:
        raise ValueError('saved public replay changed')
    pairs = [json.loads(line) for line in pairs_path.read_text().splitlines()]
    retained, inputs, counts = [], [ref(args.replay), ref(pairs_path)], Counter()
    for pair in pairs:
        if pair['new_public'] is not True or pair['private_diagnostic_label'] is not False:
            continue
        snapshot = Path(pair['closed_source_snapshot']['path'])
        if ref(snapshot) != pair['closed_source_snapshot']:
            raise ValueError('closed physical source changed')
        inputs.append(ref(snapshot))
        matches = [json.loads(line) for line in snapshot.read_text().splitlines()
                   if json.loads(line)['case']['name'] == pair['case']]
        if len(matches) != 1:
            raise ValueError('one immutable physical trial required')
        row = matches[0]
        stage = row.get('first_attempt') or {}
        truth = stage.get('private_hold_truth_v2') or {}
        if truth.get('success') is not False:
            raise ValueError('original scored label changed')
        checks = truth.get('checks') or []
        finger_all = bool(checks) and all(c['finger_contact'] is True for c in checks)
        high_all = bool(checks) and all(c['clearance_m'] >= truth['required_clearance_m'] for c in checks)
        contacts = sorted({name for c in checks for name in c.get('all_non_gripper_contact_geoms') or []})
        category = ('sustained_finger_and_lift_with_additional_contact'
                    if finger_all and high_all and contacts else 'hold_or_clearance_not_sustained')
        counts[category] += 1
        retained.append({'case': pair['case'], 'state_sha256': pair['state_sha256'],
            'original_private_score': False, 'public_verdict': True,
            'diagnostic_class': category, 'all_window_finger_contact': finger_all,
            'all_window_clearance': high_all, 'additional_contacts': contacts,
            'private_hold_evidence': truth, 'closed_source': ref(snapshot),
            'scored_label_changed': False, 'training_allowed': False})
    args.output.mkdir(parents=True, exist_ok=False)
    records = args.output / 'support_cases.jsonl'
    records.write_text(''.join(json.dumps(row) + '\n' for row in retained))
    report = {'input_replay': ref(args.replay), 'records': ref(records),
        'sources': [ref(Path(__file__)), truth_source], 'inputs': inputs,
        'counts': dict(counts), 'original_rule': 'all_current_non_gripper_contacts/2',
        'rule_location': 'robots/libero/v5_grasp_truth.py:_v2_sample_check,sustained_grasp_v2',
        'original_user_wording': 'object lifted clear of support and continuously held',
        'scope_difference': 'current rule rejects any non-gripper contact, including cabinet side or another carried object',
        'scored_labels_changed': 0, 'new_physical_trials': 0,
        'confirmation': False, 'training_allowed': False,
        'recipient': 'Codex1: reconcile metrology scope; keep current scores pending review'}
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'manifest': ref(path), 'counts': dict(counts)}))


if __name__ == '__main__':
    main()
