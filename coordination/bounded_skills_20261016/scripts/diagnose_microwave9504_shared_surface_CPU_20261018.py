# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare immutable public door measurements behind split fixture identities."""
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
directory = root/'results/bounded_skills/feasibility_20261017/job9504_120'
choices = next(directory.glob('*oracle*/choices.jsonl'))
rows = [json.loads(line) for line in choices.open()]
records = []
for index, row in enumerate(rows):
    measured = []
    for parent, detail in row.get('fixture_measurement_evidence', {}).items():
        door = detail.get('door_measurement', {})
        if not door.get('path'):
            continue
        path = Path(door['path'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == door['sha256'], path
        with np.load(path) as arrays:
            points = arrays[arrays.files[0]]
        points = np.asarray(points).reshape(-1, 3)
        measured.append((parent, door, points))
    for first_index, (first, a_ref, a) in enumerate(measured):
        for second, b_ref, b in measured[first_index+1:]:
            distances = [cKDTree(other).query(points, workers=1)[0]
                for points, other in ((a, b), (b, a))]
            normals, residuals = [], []
            for points in (a, b):
                centre = np.median(points, axis=0)
                _, axes = np.linalg.eigh(np.cov(points[:, :2].T))
                normals.append(axes[:, 0])
                residuals.append(float(np.quantile(abs((points[:, :2]-centre[:2])@axes[:, 0]), .9)))
            records.append({'row': index, 'parents': [first, second],
                'source_steps': [a_ref['source_step'], b_ref['source_step']],
                'clouds': [{'path': ref['path'], 'sha256': ref['sha256'],
                    'points': len(points), 'array_sha256': hashlib.sha256(
                        np.ascontiguousarray(points).tobytes()).hexdigest()}
                    for ref, points in ((a_ref, a), (b_ref, b))],
                'coverage_within_1um': [float(np.mean(d <= 1e-6)) for d in distances],
                'coverage_within_4mm': [float(np.mean(d <= .004)) for d in distances],
                'nearest_p50_p90_m': [np.quantile(d, [.5, .9]).tolist() for d in distances],
                'normal_agreement': float(abs(normals[0]@normals[1])),
                'normal_residual_p90_m': residuals})
report = {'choices': str(choices), 'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(),
    'records': records, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'saved public RGB-D measurement only; overlap is not endpoint success',
    'physics_steps': 0, 'gpu_used': False, 'training': False}
output = base/'reports/microwave9504_shared_surface_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
for record in records:
    print(json.dumps({k: record[k] for k in ('row', 'parents', 'source_steps',
        'coverage_within_1um', 'coverage_within_4mm', 'normal_agreement', 'normal_residual_p90_m')}))
