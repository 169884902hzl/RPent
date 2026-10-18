# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measure whether existing circular-section geometry explains omitted public pixels."""
# ruff: noqa: E402 -- CPU and immutable source selected before project imports
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--job', required=True, choices=['16', '17', '19'])
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
source = root/'source_bounded_chunk_v3_payload_interval_20261018_87ef92e'
sys.path.insert(0, str(source))
import numpy as np

from robots.libero.v5_grasp_geometry import complete_cylindrical_contact_surface

case = next(c for c in json.loads((base/'reports/9026_contact_blocker_pixels_CPU_20261018.json').read_text())['cases']
    if c['job'] == '9026_'+args.job)
points = np.asarray([view['point_m'] for view in case['views']]).reshape(-1, 1, 3)
directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+case['job'])).glob('*oracle*')
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[case['row']])
if args.job == '17':
    reference = row['public_geometry_evidence']['bounded_screen_e107_1_target']
    path = Path(reference['path'])
else:
    path = Path('/tmp/9026_'+args.job+'_candidate_r2_screens.npz')
with np.load(path) as data:
    measured = np.unique(data[data.files[0]].reshape(-1, 3), axis=0)
_, axes = np.linalg.eigh(np.cov(measured.T))
records = []
for axis in axes.T:
    started = time.perf_counter()
    matched, evidence = complete_cylindrical_contact_surface(points, measured, axis)
    records.append({'axis_xyz': axis.tolist(), 'matched': matched[:, 0].tolist(),
        'elapsed_s': time.perf_counter()-started, 'evidence': evidence})
report = {'job': case['job'], 'row': case['row'], 'source': str(source),
    'public_input': {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
    'measured_points': len(measured), 'blockers': points[:, 0].tolist(), 'records': records,
    'controls': 0, 'gpu_used': False, 'private_truth_used': False,
    'scope': 'geometry explanation only; no full-scene FP audit or physical result'}
output = base/'reports'/f'9026_{args.job}_curved_surface_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'axes': [{'matched': r['matched'], 'seconds': r['elapsed_s'],
    'sections': len(r['evidence']['sections'])} for r in records]}))
