"""Measure observed edge normals in the two original plate development states."""
# ruff: noqa: E402 -- select the recorded source and CPU before imports
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_inclined_rim_20261018_2997335'
sys.path.insert(0, str(source))

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_offline_labels import load_annotation_state

records = []
for job in ('9502_160', '9502_161'):
    directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle_k4')
    lines = (directory/'choices.jsonl').read_bytes().splitlines()
    for index in (0, 1):
        row = json.loads(lines[index])
        ref = row['private_prefix_annotation_state']
        state = load_annotation_state(ref['path'], ref['sha256'])
        adapter = state['adapter']
        for diagnostic in row['candidate_screen_diagnostics']:
            if diagnostic.get('stage') != 'measured_surface_contact' or diagnostic.get('contact_xyz_m') is None:
                continue
            key = diagnostic['anchor_id']
            # The frozen screen contains only public RGB-D and static robot geometry.
            screen = adapter._cloud_and_ik(key, contact=True)
            points = np.unique(screen.measured_target_points, axis=0)
            centre = np.median(points, axis=0)
            tree = cKDTree(points)
            sampled = np.linspace(0, len(points)-1, min(1000, len(points)), dtype=int)
            patches = []
            for point in points[sampled]:
                nearby = points[tree.query_ball_point(point, .01)]
                if len(nearby) < 12:
                    continue
                values, axes = np.linalg.eigh(np.cov(nearby.T))
                if values[1] <= 1e-8 or values[0] > .2*values[1]:
                    continue
                normal = axes[:, 0]
                if normal@(point-centre) < 0:
                    normal = -normal
                patches.append({'xyz_m': point.tolist(), 'normal_xyz': normal.tolist(),
                    'points': len(nearby), 'planarity_ratio': float(values[0]/values[1])})
            side = [patch for patch in patches if abs(patch['normal_xyz'][2]) <= .5]
            records.append({'job': job, 'row': index, 'anchor_id': key,
                'frozen_request_sha256': ref['request_sha256'], 'public_target_points': len(points),
                'public_bounds_m': np.quantile(points, [.02, .98], axis=0).tolist(),
                'selected_contact_xyz_m': diagnostic['contact_xyz_m'],
                'selected_normal_xyz': diagnostic['surface_normal_xyz'],
                'samples': len(sampled), 'planar_patches': len(patches),
                'side_patches': len(side), 'side_patch_examples': side[:20],
                'normal_abs_z_quantiles': np.quantile([abs(patch['normal_xyz'][2])
                    for patch in patches], [0., .1, .5, .9, 1.]).tolist() if patches else None})

report = {'scope': 'public measured edge-normal diagnosis; no planner, controls or truth coordinates',
    'source': str(source), 'records': records, 'gpu_used': False, 'physics_steps': 0,
    'private_truth_used': False, 'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/thin_surface_normals_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
for record in records:
    print(json.dumps({key: value for key, value in record.items() if key != 'side_patch_examples'}))
