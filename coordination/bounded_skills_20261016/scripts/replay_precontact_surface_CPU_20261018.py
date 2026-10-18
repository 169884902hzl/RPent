# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Replay pre-lift contact geometry from two saved public RGB-D captures."""
# ruff: noqa: E402 -- pin the selected source before robot imports
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--job', default='8173_24')
parser.add_argument('--row', type=int, default=2)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--working-adapter', type=Path, required=True)
parser.add_argument('--working-payload', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from robots.libero.bounded_motion import MotionConfig, SmoothMotion
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_geometric_grasp import _voxel, panda_geometry
from robots.libero.v5_state import Entity

if args.working_payload:
    import robots.libero.bounded_payload as payload

    spec = importlib.util.spec_from_file_location('precontact_candidate_payload', args.working_payload)
    candidate_payload = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_payload)
    payload._surface_registration = candidate_payload._surface_registration

root = Path('/public/home/sunyihan/rpent_libero_eval')
directory = next((root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)).glob('*oracle*'))
prefix = (directory/'choices.jsonl').read_bytes().splitlines()
rows = [json.loads(line) for line in prefix]
row = rows[args.row]
diagnostic = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'lift')
key = diagnostic['parameters']['anchor_id']
blockers = np.unique([p for points in diagnostic['public_scene_collision_points'].values()
                      for p in points], axis=0)
step = row['public_geometry_evidence'][f'bounded_screen_{key}_1_scene']['capture_step']
robot = next(control['after'] for old in reversed(rows[:args.row])
             for detail in reversed(old['execution_details'])
             for control in reversed(detail.get('execution', {}).get('trace', [])))
for field in ('eef_xyz_m', 'eef_quat_xyzw'):
    np.testing.assert_allclose(robot[field], row['request']['robot'][field], atol=1e-10)


def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    if path.suffix == '.png':
        return np.asarray(Image.open(path))
    with np.load(path) as stream:
        return stream[stream.files[0]]


def frame(name):
    return load(directory/name/(f'{step:02d}'+Path(name).suffix))


views = {}
for camera, artifact in row['perception_evidence'][key]['sam_mask_files'].items():
    assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest() == artifact['sha256']
    views[camera] = {'source_step': step,
        'xyz_world': frame(camera+'_world_high.npz')[load(artifact['path']).astype(bool)]}
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
       'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
adapter.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
adapter.geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
adapter.robot_xml = xml.parent.parent/'robots/panda/robot.xml'
adapter._instance_cache, adapter._screen_cache, adapter._base_geometry = {}, {}, None
adapter.held = adapter.active = adapter.payload_reference = adapter.withdrawal_contact = None
adapter.instance_boundary_evidence, adapter.committed_grasps, adapter.plans = {}, {}, {}
adapter.record_public_geometry = False
adapter._self_filtered_capture = None
entities = {}
for anchor in row['request']['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, step)
adapter.scene = SimpleNamespace(entities=entities, measurement_clouds_by_view={key: views}, measurement_clouds={})
adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step, load=frame)))
adapter._cloud_and_ik()
instance = adapter._instance_pixels(key)
baseline_dist = cKDTree(instance).query(blockers)[0]

earlier = next(record for record in rows[:args.row]
    if f'bounded_screen_{key}_1_target' in record['public_geometry_evidence']
    and key in record['perception_evidence'])
old_step = earlier['public_geometry_evidence'][f'bounded_screen_{key}_1_target']['capture_step']
old_robot = next(control['before'] for detail in earlier['execution_details']
    for control in detail.get('execution', {}).get('trace', []))
old_obs = {'robot0_eef_pos': old_robot['eef_xyz_m'], 'robot0_eef_quat': old_robot['eef_quat_xyzw'],
    'robot0_gripper_qpos': old_robot['finger_positions_m'], 'robot0_joint_pos': old_robot['joint_positions_rad']}
old = copy.copy(adapter)
old.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: old_obs))
old._instance_cache, old._screen_cache, old._base_geometry = {}, {}, None
old.instance_boundary_evidence = {}
old_entities, old_views = {}, {}
for a in earlier['request']['anchors']:
    centre, size = np.asarray(a['xyz_m']), np.asarray(a['size_m'])
    old_entities[a['id']] = Entity(a['id'], a['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, old_step)
def old_frame(name):
    return load(directory/name/(f'{old_step:02d}'+Path(name).suffix))
for camera, artifact in earlier['perception_evidence'][key]['sam_mask_files'].items():
    old_views[camera] = {'source_step': old_step,
        'xyz_world': old_frame(camera+'_world_high.npz')[load(artifact['path']).astype(bool)]}
old.scene = SimpleNamespace(entities=old_entities,
    measurement_clouds_by_view={key: old_views}, measurement_clouds={})
old.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=old_step, load=old_frame)))
old._cloud_and_ik()
reference = old._instance_pixels(key)


adapter.config = MotionConfig()
tail = [control['after'] for previous in rows[:args.row] for detail in previous['execution_details']
        for control in detail.get('execution', {}).get('trace', [])][-4:]
adapter.p._bounded_motion_samples = list(enumerate(tail))
adapter.p._bounded_control_index = len(tail)-1
adapter.active = key
adapter.committed_grasps[key] = {'plan': {}, 'instance_reference': {
    'xyz_world': reference, 'source_step': old_step, 'stationary_scene': _voxel(old._base_geometry[0][
        cKDTree(reference).query(old._base_geometry[0])[0] > 1e-6], .001)}}
waypoint = {'xyz_m': (np.asarray(robot['eef_xyz_m'])+[0., 0., .1]).tolist(),
            'quat_xyzw': robot['eef_quat_xyzw']}
spec = importlib.util.spec_from_file_location('precontact_candidate_adapter', args.working_adapter)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
stages, surfaces = [], {}
for name, implementation in [('baseline', MeasuredSkillAdapter), ('registered', module.MeasuredSkillAdapter)]:
    adapter.__class__ = implementation
    adapter._instance_cache, adapter._screen_cache = {}, {}
    surface = adapter._contact_pixels(key)
    surfaces[name] = surface
    screen = adapter._cloud_and_ik(key, contact=True)
    _, _, _, evidence = SmoothMotion(adapter.p, screen, adapter.config).prepare([waypoint])
    remaining = np.unique([point for cloud in evidence.get('public_scene_collision_points', {}).values()
        for point in cloud], axis=0).reshape(-1, 3)
    stationary = adapter.committed_grasps[key]['instance_reference']['stationary_scene']
    trees = {label: cKDTree(points) for label, points in (
        ('current_instance', instance), ('old_reference', reference), ('stationary_scene', stationary))}
    neighbourhoods = [{'xyz_m': point.tolist(),
        **{label+'_distance_m': float(tree.query(point)[0]) for label, tree in trees.items()}}
        for point in remaining]
    stages.append({'name': name, 'route_screen': evidence,
        'blocker_distances_m': cKDTree(surface).query(blockers)[0].tolist(),
        'remaining_scene_blocker_neighbourhoods': neighbourhoods,
        'boundary': copy.deepcopy(adapter.instance_boundary_evidence[key])})
before, after = surfaces['baseline'], surfaces['registered']
added = after[cKDTree(before).query(after)[0] > 1e-6]
removed = before[cKDTree(after).query(before)[0] > 1e-6]
delta_path = args.output.with_suffix('.npz')
np.savez_compressed(delta_path, added=np.unique(added, axis=0), removed=np.unique(removed, axis=0))
report = {'scope': 'CPU saved-public precontact membership and lift-route replay; zero controls',
    'job': args.job, 'row': args.row, 'anchor_id': key, 'capture_step': step,
    'reference_capture_step': old_step, 'stages': stages,
    'source': str(args.source), 'source_sha256': hashlib.sha256(
        (args.source/'robots/libero/bounded_skills.py').read_bytes()).hexdigest(),
    'candidate_sha256': hashlib.sha256(args.working_adapter.read_bytes()).hexdigest(),
    'candidate_payload': None if args.working_payload is None else {
        'path': str(args.working_payload),
        'sha256': hashlib.sha256(args.working_payload.read_bytes()).hexdigest()},
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'membership_delta': {'path': str(delta_path), 'sha256': hashlib.sha256(delta_path.read_bytes()).hexdigest(),
        'added': len(np.unique(added, axis=0)), 'removed': len(np.unique(removed, axis=0))},
    'controls': 0, 'gpu_used': False, 'private_truth_used': False, 'training': False}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'delta': report['membership_delta'],
    'screens': [(stage['name'], stage['route_screen']['passed']) for stage in stages]}))
