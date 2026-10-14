"""Diagnose saved selection bindings; private positions never enter control."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    indexed = defaultdict(list)
    for row in map(json.loads, args.rows.open()):
        indexed[Path(row['input'])].append(row)
    records, sources = [], []
    for path, rows in indexed.items():
        evidence = pin(path)
        if any(r['input_sha256'] != evidence['sha256'] for r in rows):
            raise ValueError('saved physical ledger changed')
        sources.append(evidence)
        requested = {row['line']: row for row in rows}
        for line_number, line in enumerate(path.open(), 1):
            if line_number not in requested:
                continue
            row, raw = requested[line_number], json.loads(line)
            if row['case'] != raw['case']['name']:
                raise ValueError('case identity mismatch')
            case = raw['case']
            layout_path = Path(case['registered_layout_state']['path'])
            if pin(layout_path) != case['registered_layout_state']:
                raise ValueError('registered layout changed')
            layout = json.loads(layout_path.read_text())
            if layout['state_sha256'] != row['state_sha256']:
                raise ValueError('registered state mismatch')
            geometry = layout['preparation_provenance']['settled_geometry']
            target = np.asarray(geometry[case['object_symbol']], dtype=float)
            first = raw.get('first_attempt') or {}
            receipt = first.get('receipt') or {}
            entity_id = receipt.get('object')
            public = next((e for e in (first.get('public_before') or {}).get('entities', [])
                           if e['id'] == entity_id), None)
            observed = np.asarray(public['xyz'], dtype=float) if public else None
            nearest = min(geometry, key=lambda name: np.linalg.norm(
                np.asarray(geometry[name]) - observed)) if observed is not None else None
            distance = float(np.linalg.norm(target - observed)) if observed is not None else None
            truth = first.get('private_hold_truth_v3') or {}
            reasons = Counter(c['unknown_reason'] for c in truth.get('checks', [])
                              if c.get('unknown_reason'))
            state_path = Path(raw['output_dir']) / 'states.json'
            wrist_tilt = None
            if state_path.is_file():
                from scipy.spatial.transform import Rotation
                state = json.loads(state_path.read_text())['steps'][0]['state']
                axis = Rotation.from_quat(state['robot0_eef_quat']).as_matrix()[:, 2]
                wrist_tilt = float(np.degrees(np.arccos(np.clip(-axis[2], -1, 1))))
            records.append({'case': row['case'], 'type': row['type'],
                'state_sha256': row['state_sha256'], 'layout_seed': case['layout_seed'],
                'input': evidence, 'line': line_number,
                'registered_layout': case['registered_layout_state'],
                'target_symbol': case['object_symbol'],
                'target_initial_body_origin_xyz_private_diagnostic': target.tolist(),
                'layout_validity_at_registration': layout['status'],
                'registered_invalid_reasons': layout['invalid_reasons'],
                'public_bound_entity': public,
                'public_to_registered_target_distance_m_diagnostic': distance,
                'nearest_initial_body_to_public_point_diagnostic': nearest,
                'nearest_body_distance_m_diagnostic': float(np.linalg.norm(
                    np.asarray(geometry[nearest]) - observed)) if nearest else None,
                'initial_downward_wrist_tilt_degrees_public': wrist_tilt,
                'v3_success': row['registered_v3'], 'v3_unknown_reasons': dict(reasons),
                'public_grasp_verified': row['public'],
                'private_diagnostic_only': True, 'control_or_verifier_changed': False})
    groups = {}
    for category in sorted({r['type'] for r in records}):
        rows = [r for r in records if r['type'] == category]
        distances = [r['public_to_registered_target_distance_m_diagnostic'] for r in rows
                     if r['public_to_registered_target_distance_m_diagnostic'] is not None]
        tilts = [r['initial_downward_wrist_tilt_degrees_public'] for r in rows
                 if r['initial_downward_wrist_tilt_degrees_public'] is not None]
        groups[category] = {'registered_n': len(rows), 'public_binding_measured_n': len(distances),
            'public_to_target_distance_median_p90_max': np.quantile(distances, [.5, .9, 1]).tolist()
                if distances else None,
            'public_to_target_distance_over_10cm_diagnostic_n': sum(d > .10 for d in distances),
            'public_to_target_distance_over_50cm_diagnostic_n': sum(d > .50 for d in distances),
            'different_nearest_initial_body_n_diagnostic': sum(
                r['nearest_initial_body_to_public_point_diagnostic'] is not None and
                r['nearest_initial_body_to_public_point_diagnostic'] != r['target_symbol'] for r in rows),
            'v3_unknown_n': sum(r['v3_success'] is None for r in rows),
            'v3_unknown_reason_counts': dict(sum((Counter(r['v3_unknown_reasons']) for r in rows), Counter())),
            'initial_public_wrist_tilt_median_p90_max_degrees': np.quantile(tilts, [.5, .9, 1]).tolist()
                if tilts else None}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    producer = args.output / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    manifest = {'producer': pin(producer), 'input_rows': pin(args.rows), 'inputs': sources,
        'groups': groups, 'registered_n': len(records), 'diagnostic_thresholds_not_scoring_rules': True,
        'runtime_or_v3_changed': False, 'historical_denominators_unchanged': True,
        'confirmation_or_training_execution': False, 'training_allowed': False,
        'limits': ['Distance is to the initial body origin, not a ground truth surface centre.',
            'Nearest body is diagnostic; it does not identify a mask by itself.',
            'Large displacement already present in the registered layout is not a contact failure.',
            'Initial wrist tilt alone does not establish a pose-control failure.']}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'registered_n': len(records), 'groups': groups}))


if __name__ == '__main__':
    main()
