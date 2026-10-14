"""Explain all 13 width anomalies using preserved public depth evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_grasp_geometry import clean_object_mask


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('anomalies', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for line in (args.anomalies / 'records.jsonl').open():
        row = json.loads(line)
        if row['category'] != 'box':
            continue
        obj = row['selected_entity_before']
        extent = np.asarray(obj['upper']) - obj['lower']
        item = {'case': row['case'], 'state_sha256': row['state_sha256'],
                'initial_entity': obj, 'initial_axis_extent_m': extent.tolist(),
                'initial_xy_narrow_m': float(min(extent[:2])),
                'refined_planned_width_m': row['plan']['measured_width_m'],
                'original_sam_mask_saved': False, 'exact_segmentation_cause': 'not_recoverable',
                'evidence_scope': 'recorded_public_bbox_reconstruction_not_original_sam_cloud',
                'views': [], 'private_pose_used': False, 'training_allowed': False}
        for view in row.get('public_clouds', []):
            path = Path(view['world_input']['path'])
            if pin(path)['sha256'] != view['world_input']['sha256']:
                raise ValueError('public depth evidence changed')
            with np.load(path) as archive:
                world = archive[archive.files[0]].astype(float)
            lo, hi = np.asarray(obj['lower']), np.asarray(obj['upper'])
            mask = (np.isfinite(world).all(axis=2)
                    & ((world >= lo - .005) & (world <= hi + .005)).all(axis=2))
            clean, components = clean_object_mask(world, mask, prior_lower=lo, prior_upper=hi)
            points = world[clean]
            bounds = np.quantile(points, [.02, .98], axis=0) if len(points) else None
            d = {'camera': view['camera'], 'input': pin(path), 'component_evidence': components,
                 'cleaned_bounds': bounds.tolist() if bounds is not None else None,
                 'cleaned_xy_narrow_m': float(min(bounds[1, :2] - bounds[0, :2]))
                 if bounds is not None else None}
            item['views'].append(d)
        item['explanation'] = 'old_mask_absent; rotated_AABB_and_grasp_axis_width_not_directly_comparable'
        rows.append(item)
    if len(rows) != 13:
        raise ValueError('must account for every registered width anomaly')
    args.output.mkdir(parents=True, exist_ok=False)
    records = args.output / 'records.jsonl'
    records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    summary = {'n': len(rows), 'explanations': dict(Counter(r['explanation'] for r in rows)),
               'records': pin(records), 'inputs': pin(args.anomalies / 'records.jsonl'),
               'producer': pin(Path(__file__)), 'runtime_geometry': pin(Path(clean_object_mask.__code__.co_filename)),
               'limitations': ['A bounds reconstruction cannot establish which original SAM pixels were contaminated.',
                              'World-axis AABB width and the planner closing-axis width are different measurements.',
                              'Post-cleanup dimensions on reconstructed masks are diagnostic, not paired physical outcomes.'],
               'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
