# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Locate a rejected lift pixel relative to measured precontact support."""
# ruff: noqa: E402 -- select the pinned source before robot imports
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--preserve-full-frame-interior', action='store_true')
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers,
    gripper_visual_boxes,
    remove_current_gripper,
    remove_visual_robot,
)
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_geometry import (
    complete_contact_surface,
    complete_planar_boundary,
)
from robots.libero.v5_grasp_kinematics import PublicPoseScreen

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = next((root/'results/bounded_skills/feasibility_20261017/job8870_3').glob('*oracle*'))
raw = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
row, step = rows[2], 4
robot = next(control['after'] for previous in reversed(rows[:2])
    for detail in reversed(previous['execution_details'])
    for control in reversed(detail.get('execution', {}).get('trace', [])))
np.testing.assert_allclose(robot['eef_xyz_m'], row['request']['robot']['eef_xyz_m'])


def load(path):
    with np.load(path) as archive:
        return archive[archive.files[0]]


old = load(directory/'bounded_precontact_e61_target.npz/00.npz')
block = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'lift')
points = np.unique([p for values in block['public_scene_collision_points'].values()
                   for p in values], axis=0)
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
geometry = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
    robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'], warm_start=True)
results = []
for camera in ('agentview', 'wrist'):
    world = load(directory/(camera+'_world_high.npz')/f'{step:02d}.npz')
    raw_world = world.copy()
    flat = world.reshape(-1, 3)
    filtered, _ = remove_current_gripper(flat, robot['eef_xyz_m'], robot['eef_quat_xyzw'],
        geometry, robot['gripper_opening_m'])
    filtered, _ = ik.remove_measured_arm(filtered)
    filtered, _ = remove_visual_robot(filtered, ik)
    ids = np.flatnonzero(np.isfinite(flat).all(axis=1))
    present = cKDTree(filtered).query(flat[ids],
        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
    flat[:] = np.nan
    flat[ids[present]] = raw_world.reshape(-1, 3)[ids[present]]
    mask, evidence = complete_contact_surface(world, old, current_boundary=True)
    extent = ((world >= old.min(0)-.001).all(2) & (world <= old.max(0)+.001).all(2))
    bounded, bounded_evidence = complete_contact_surface(world, old)
    if args.preserve_full_frame_interior:
        bounded = mask & extent
    local, local_evidence = complete_planar_boundary(world, bounded)
    raw_flat = raw_world.reshape(-1, 3)
    valid = np.flatnonzero(np.isfinite(raw_flat).all(1))
    distances, near = cKDTree(raw_flat[valid]).query(points)
    ys, xs = np.unravel_index(valid[near], world.shape[:2])
    added_y, added_x = np.nonzero(local & ~bounded)
    results.append({'camera': camera, 'pixels': list(zip(xs.tolist(), ys.tolist())),
        'raw_distance_m': distances.tolist(), 'current_boundary_member': mask[ys, xs].tolist(),
        'after_prior_extent_clip_member': (mask & extent)[ys, xs].tolist(),
        'one_current_local_plane_step_member': local[ys, xs].tolist(),
        'one_current_local_plane_step': local_evidence,
        'new_current_plane_pixels': {
            'xy': np.stack([added_x, added_y], axis=1).tolist(),
            'xyz_m': world[added_y, added_x].tolist()},
        'bounded_without_full_frame': {
            'old_interior_missing': int(((mask & extent) & ~bounded).sum()),
            'extra_interior': int((bounded & ~(mask & extent)).sum()),
            'evidence': bounded_evidence},
        'prior_extent_member': extent[ys, xs].tolist(), 'evidence': evidence})
report = {'job': '8870_3', 'row': 2, 'points_m': points.tolist(),
    'preserve_full_frame_interior': args.preserve_full_frame_interior,
    'reference_bounds_m': [old.min(0).tolist(), old.max(0).tolist()],
    'prior_surface_distance_m': cKDTree(old).query(points)[0].tolist(), 'views': results,
    'input_sha256': hashlib.sha256(raw).hexdigest(), 'source': str(args.source),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'private_truth_used': False, 'controls': 0, 'training': False, 'confirmation': False}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'views': [{k: v for k, v in result.items() if k != 'evidence'} for result in results]}))
