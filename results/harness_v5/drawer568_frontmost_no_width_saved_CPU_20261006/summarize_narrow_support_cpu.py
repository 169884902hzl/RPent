"""Expose per-camera narrow support and paired-public-view consistency."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


OUT = Path(__file__).resolve().parent / 'comparison'
RECORDS = OUT / 'same20_frontmost_comparison.jsonl'


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


counts, narrow, changes, selected_rows = Counter(), [], [], []
items = list(map(json.loads, RECORDS.read_text().splitlines()))
for item in items:
    for phase, capture in item['captures'].items():
        counts['phases'] += 1
        counts['phase_crossview_disagreement'] += bool(capture['crossview_disagreements'])
        for camera, view in capture['views'].items():
            fit = view['frontmost_original_gates'].get('moving')
            original = view['v7'].get('moving')
            shape = view['selected_support']['moving']
            parent_width = view['moving_candidates'][0]['parent_width_m']
            record = {'case': item['case'], 'phase': phase, 'camera': camera,
                      'public_world': view['public_RGBD'], 'fresh_pair': item['fresh_before_after_public_steps'],
                      'selected': fit is not None, 'v7_selected': original is not None,
                      'width_m': shape['width_m'], 'height_m': shape['height_m'], 'points': shape['points'],
                      'width_fraction': shape['width_m'] / parent_width if fit is not None else None,
                      'residual_p90_m': fit['residual_p90_m'] if fit is not None else None,
                      'centre': fit['centre'] if fit is not None else None}
            if fit is not None:
                counts['camera_moving_fits'] += 1
                if record['width_fraction'] < .5:
                    counts['camera_moving_fits_narrower_than_v7_gate'] += 1
                    other = capture['views']['wrist' if camera == 'agentview' else 'agentview']['frontmost_original_gates'].get('moving')
                    if other is not None:
                        normal = np.asarray(other['normal_xy'])
                        record['other_camera_plane_normal_distance_m'] = abs(float((np.asarray(fit['centre'][:2]) - other['centre'][:2]) @ normal))
                        record['other_camera_plane_normal_cosine'] = abs(float(np.asarray(fit['normal_xy']) @ normal))
                    else:
                        record['other_camera_moving_plane_missing'] = True
                    narrow.append(record)
            if fit != original:
                changes.append(record)
            selected_rows.append(record)
table = OUT / 'selected_percamera_planes.tsv'
fields = ['case', 'phase', 'camera', 'fresh_pair', 'selected', 'v7_selected', 'width_m', 'height_m',
          'points', 'width_fraction', 'residual_p90_m']
with table.open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter='\t')
    writer.writeheader()
    writer.writerows({key: record[key] for key in fields} for record in selected_rows)
analysis = {'scope': 'Public candidate support only; compare per-camera fits accepted after removing extra width gate',
            'records': ref(RECORDS), 'main_report': ref(OUT / 'report.json'), 'producer': ref(__file__),
            'counts': dict(counts), 'newly_accepted_percamera_planes': changes,
            'selected_narrow_percamera_planes': narrow,
            'distinct_narrow_public_world_files': len({item['public_world']['path'] for item in narrow}),
            'joined_effect': 'Only t23/s10 after changes in the40 joined phase selections; no new crossview disagreement in any phase',
            'ownership_limit': 'Public support and camera agreement cannot certify semantic ownership or physical endpoint truth; none of those labels entered selection',
            'duplicate_capture_limit': 't28/s10 before and after refer to the same step0 public wrist file and are not independent temporal evidence',
            'candidate_table': ref(OUT / 'candidate_planes.tsv'), 'selected_camera_table': ref(table),
            'private_qpos_or_truth_used': False, 'new_model_calls': 0, 'new_physics': 0,
            'shared_runtime_or_original_labels_changed': False}
path = OUT / 'narrow_support_analysis.json'
path.write_text(json.dumps(analysis, indent=2) + '\n')
print(json.dumps({'analysis': ref(path), 'selected_camera_table': ref(table), 'counts': dict(counts),
                  'newly_accepted_percamera_planes': changes}))
