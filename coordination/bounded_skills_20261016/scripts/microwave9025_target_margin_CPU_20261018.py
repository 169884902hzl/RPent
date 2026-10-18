# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measure saved target/finger clearance using public depth and proprioception."""
# ruff: noqa: E402 -- immutable source and CPU selected before geometry imports
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
receipt = json.loads((base/'reports/chunk_v3_panel_recovery_20261018_full_submission.json').read_text())
sys.path.insert(0, receipt['snapshot'])

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_geometric_grasp import panda_geometry

updated_path = Path('/tmp/bounded_screen_target_margin_20261018.py')
spec = importlib.util.spec_from_file_location('target_margin_screen', updated_path)
updated = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updated)

directory = root/'results/bounded_skills/feasibility_20261017/job9025_120'
choices = next(directory.glob('*oracle_k4/choices.jsonl'))
raw = choices.read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
results = []
for index in (7, 8, 9, 10):
    if index >= len(rows):
        continue
    row = rows[index]
    robot = row['request']['robot']
    traces = [item for detail in row['execution_details']
              for item in detail.get('execution', {}).get('trace', [])]
    if not traces:
        results.append({'index': index, 'reason': 'no_public_execution_trace'})
        continue
    before = traces[0]['before']
    assert np.allclose(before['eef_xyz_m'], robot['eef_xyz_m'], atol=1e-10)
    geometry = gripper_at_measured_fingers(panda_geometry(xml), before['finger_positions_m'])
    reference = row['public_geometry_evidence'].get('bounded_screen_e114_0_target')
    if reference is None:
        results.append({'index': index, 'reason': 'no_target_screen_record'})
        continue
    cloud_raw = Path(reference['path']).read_bytes()
    assert hashlib.sha256(cloud_raw).hexdigest() == reference['sha256']
    with np.load(reference['path']) as archive:
        target = archive[archive.files[0]]
    screen = PublicRouteScreen([[10., 10., 10.]], geometry,
        SimpleNamespace(check=lambda *args: {'solution_found': True}),
        opening=robot['gripper_opening_m'], contact_points=target)
    pose = {'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']}
    repaired = updated.PublicRouteScreen([[10., 10., 10.]], geometry,
        SimpleNamespace(check=lambda *args: {'solution_found': True}),
        opening=robot['gripper_opening_m'], contact_points=target, initial_pose=pose)
    routes = []
    for axis in range(3):
        for direction in (-1, 1):
            endpoint = np.asarray(pose['xyz_m']).copy()
            endpoint[axis] += direction*.01
            route = [pose, {**pose, 'xyz_m': endpoint.tolist()}]
            a, b = screen(route), repaired(route)
            routes.append({'axis': 'xyz'[axis], 'distance_m': direction*.01,
                'old_passed': a['passed'], 'new_passed': b['passed'],
                'old_reason': a['reason'], 'new_reason': b['reason']})
    rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
    site = rotation@Rotation.from_euler('z', -np.pi/2).as_matrix()
    local = (target-robot['eef_xyz_m'])@site
    boxes = []
    for box in geometry['boxes']:
        near = ((local >= np.asarray(box['lower'])-.004)
                & (local <= np.asarray(box['upper'])+.004)).all(axis=1)
        distance = screen._halfspace_distance(local[near], box)
        hits = distance[distance <= .004]
        boxes.append({'name': box['name'], 'hits': len(hits),
            'inside_mesh': int((hits <= 0.).sum()),
            'positive_margin': int((hits > 0.).sum()),
            'min_signed_distance_m': float(hits.min()) if len(hits) else None,
            'max_signed_distance_m': float(hits.max()) if len(hits) else None})
    results.append({'index': index, 'robot': robot,
        'finger_positions_m': before['finger_positions_m'], 'target_reference': reference,
        'target_points': len(target), 'boxes': boxes, 'geometry_only_routes': routes})
report = {'scope': 'saved public RGB-D and execution proprioception; zero controls',
    'source_commit': receipt['source_commit'], 'snapshot': receipt['snapshot'],
    'choices_path': str(choices), 'choices_sha256': hashlib.sha256(raw).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'updated_screen_sha256': hashlib.sha256(updated_path.read_bytes()).hexdigest(),
    'private_truth_used': False, 'gpu_used': False, 'training': False, 'results': results}
output = base/'reports/microwave9025_target_margin_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
