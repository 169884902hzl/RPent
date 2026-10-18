# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Record the rejected public ICP path without changing runtime ownership."""
# ruff: noqa: E402 -- CPU-only imports after environment selection
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def voxel(points):
    points = np.asarray(points, float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    _, ids = np.unique(np.floor(points/.001).astype(int), axis=0, return_index=True)
    return points[np.sort(ids)]


reports = []
for job in ('16', '19'):
    path = Path('/tmp/9026_'+job+'_registration_CPU_registration_0.npz')
    with np.load(path) as data:
        predicted, measured = data['predicted'], data['current']
    source, target = voxel(predicted), voxel(measured)
    source = source[::max(1, len(source)//8000)]
    centre = source.mean(0)
    rotation, shift = np.eye(3), np.zeros(3)
    tree = cKDTree(target)
    records = []
    for iteration in range(30):
        transformed = (source-centre)@rotation.T+centre+shift
        distance, ids = tree.query(transformed)
        supported = distance <= .008
        if supported.sum() < 40 or supported.mean() < .5:
            break
        a, b = transformed[supported], target[ids[supported]]
        ac, bc = a.mean(0), b.mean(0)
        u, _, vt = np.linalg.svd((a-ac).T@(b-bc))
        turn = vt.T@u.T
        if np.linalg.det(turn) < 0:
            vt[-1] *= -1
            turn = vt.T@u.T
        delta = bc-ac@turn.T
        shift = (centre+shift)@turn.T+delta-centre
        rotation = turn@rotation
        corrected = (predicted-centre)@rotation.T+centre+shift
        displacement = np.linalg.norm(corrected-predicted, axis=1)
        angle = float(Rotation.from_matrix(rotation).magnitude())
        after = tree.query((source-centre)@rotation.T+centre+shift)[0]
        change = (a-ac)@turn.T+bc-a
        records.append({'iteration': iteration, 'supported_fraction': float(supported.mean()),
            'rotation_rad': angle, 'maximum_surface_displacement_m': float(displacement.max()),
            'median_residual_m': float(np.median(after)), 'translation_m': shift.tolist(),
            'existing_rotation_gate_passes': angle <= .1,
            'existing_displacement_gate_passes': bool(displacement.max() <= .015)})
        if np.linalg.norm(change, axis=1).max() < .00001:
            break
    reports.append({'job': '9026_'+job, 'public_inputs': {'path': str(path),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, 'iterations': records})
output = Path('/public/home/sunyihan/rpent_libero_eval/coordination/bounded_skills_20261016/reports/'
    '9026_registration_path_CPU_20261018.json')
report = {'records': reports, 'controls': 0, 'gpu_used': False, 'private_truth_used': False,
    'runtime_membership_changed': False,
    'scope': 'Continue rejected fit for diagnosis only; no transform is accepted or deployed.',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
