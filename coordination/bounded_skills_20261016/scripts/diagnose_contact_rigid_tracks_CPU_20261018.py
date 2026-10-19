# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Test rigid consistency of saved public RGB-D feature correspondences."""
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

base = Path('/public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016')
input_path = base/'reports/contact_feature_tracks_CPU_20261018_r2.json'
rows = json.loads(input_path.read_text())['records']


def rigid(before, after):
    a, b = before.mean(0), after.mean(0)
    u, _, vt = np.linalg.svd((before-a).T@(after-b))
    matrix = vt.T@u.T
    if np.linalg.det(matrix) < 0:
        vt[-1] *= -1
        matrix = vt.T@u.T
    return matrix, b-matrix@a


records = []
for row in rows:
    record = {k: row[k] for k in ('job', 'row', 'camera', 'before_capture_step', 'after_capture_step')}
    count = row.get('valid_tracks', 0)
    if count < 8:
        records.append({**record, 'accepted': False, 'reason': 'feature_correspondences_missing'})
        continue
    worlds = []
    for file in row['files']:
        if not file['path'].endswith('.npz'):
            continue
        raw = Path(file['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == file['sha256']
        with np.load(file['path']) as arrays:
            worlds.append(arrays[arrays.files[0]])
    before, after = [world[np.rint(row[key]).astype(int)[:, 1], np.rint(row[key]).astype(int)[:, 0]]
        for world, key in zip(worlds, ('tracks_before_px', 'tracks_after_px'))]
    best = None
    for ids in itertools.combinations(range(count), 3):
        selected = np.array(ids)
        spread = np.linalg.svd(before[selected]-before[selected].mean(0), compute_uv=False)
        if spread[1] < .002:
            continue
        matrix, shift = rigid(before[selected], after[selected])
        residual = np.linalg.norm(before@matrix.T+shift-after, axis=1)
        mask = residual <= .003
        score = (int(mask.sum()), -float(np.median(residual)))
        if best is None or score > best[0]:
            best = score, mask
    if best is None:
        records.append({**record, 'accepted': False, 'reason': 'noncollinear_features_missing'})
        continue
    mask = best[1]
    matrix, shift = rigid(before[mask], after[mask])
    residual = np.linalg.norm(before@matrix.T+shift-after, axis=1)
    support = residual <= .003
    displacement = before[support]@matrix.T+shift-before[support]
    accepted = support.sum() >= 8 and support.mean() >= .7
    record.update(accepted=bool(accepted), samples=count, inliers=int(support.sum()),
        inlier_fraction=float(support.mean()), rotation_rad=float(Rotation.from_matrix(matrix).magnitude()),
        rotation_matrix=matrix.tolist(), translation_m=shift.tolist(),
        median_material_displacement_m=np.median(displacement, axis=0).tolist(),
        residuals_m=residual.tolist())
    records.append(record)
    print(json.dumps({k: record[k] for k in ('job', 'row', 'camera', 'accepted', 'samples',
        'inliers', 'rotation_rad', 'median_material_displacement_m')}), flush=True)
report = {'input': str(input_path), 'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'records': records,
    'physics_steps': 0, 'gpu_used': False, 'private_pose_used': False, 'runtime_changed': False,
    'scope': 'Rigid consistency diagnostic, not a validated runtime motion verifier'}
with (base/'reports/contact_rigid_tracks_CPU_20261018.json').open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
