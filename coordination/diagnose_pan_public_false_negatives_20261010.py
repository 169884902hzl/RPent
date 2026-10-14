"""Classify the saved public reasons for connected-handle pan false negatives."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INPUT = ROOT / 'coordination/geometric_grasp_first_round_closed_20261010_r1/rows.jsonl'
OUT = ROOT / 'coordination/pan_connected_handle_public_false_negatives_20261010_r1'


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUT.mkdir(exist_ok=False)
    records, counts = [], Counter()
    for row in map(json.loads, INPUT.open()):
        if ('frypan_connected_handle' not in row['group']
                or row['registered_v3'] is not True or row['public'] is not False):
            continue
        path = ROOT / row['input']
        attempt = json.loads(path.read_text().splitlines()[row['line'] - 1])['first_attempt']
        pair = attempt['verification_measurements']['independent_grasp']
        frames = []
        rejected = set()
        for frame in pair['frames']:
            views = {}
            for camera, view in frame['per_view'].items():
                conditions = view.get('conditions', {})
                rejected.update(key for key, value in conditions.items() if value is False)
                views[camera] = {key: view.get(key) for key in
                    ('current_measurement', 'measurement', 'conditions', 'reason',
                     'lower_lift_m', 'original_support_clearance_m', 'finger_geometry')}
            frames.append({'eef_xyz': frame['eef_xyz'], 'opening_m': frame['opening_m'],
                           'per_view': views})
        counts[';'.join(sorted(rejected))] += 1
        records.append({'case': row['case'], 'state_sha256': row['state_sha256'],
            'input': pin(path), 'line': row['line'], 'registered_v3': True, 'public': False,
            'rejected_public_conditions': sorted(rejected), 'public_frames': frames,
            'private_evidence_used_for_public_conditions': False,
            'classification_only_no_new_verdict': True})
    output = OUT / 'records.jsonl'
    output.write_text(''.join(json.dumps(r) + '\n' for r in records))
    manifest = {'producer': pin(Path(__file__)), 'input': pin(INPUT), 'records': pin(output),
        'false_negative_n': len(records), 'public_rejection_counts': dict(counts),
        'scope': 'saved public conditions; v3 selects diagnostic cases only',
        'limitations': ['No coupled motion was measured in these stationary frames.',
            'Object body outside the finger volume does not measure hidden handle contact.',
            'No historical grasp verdict or locked v3 truth was changed.'],
        'training_allowed': False}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
