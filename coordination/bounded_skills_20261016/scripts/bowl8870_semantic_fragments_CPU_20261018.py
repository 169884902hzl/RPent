# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Replay saved public membership and the rejected carry route; no controls."""
# ruff: noqa: E402 -- pin the requested source before importing robot modules
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--without-fragments', action='store_true')
parser.add_argument('--precontact', action='store_true')
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from robots.libero.bounded_motion import MotionConfig, SmoothMotion
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_state import Entity

if args.without_fragments:
    from robots.libero import bounded_payload
    original_membership = bounded_payload.moving_payload_pixels

    def without_fragments(*args, **kwargs):
        kwargs.pop('current_semantic_target', None)
        return original_membership(*args, **kwargs)

    bounded_payload.moving_payload_pixels = without_fragments

root = Path('/public/home/sunyihan/rpent_libero_eval')
job = '8870_3' if args.precontact else '8870_2'
directory = next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*'))
raw = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
row, key = rows[2], 'e61' if args.precontact else 'e15'
step = 4 if args.precontact else 5
robot = next(control['after'] for previous in reversed(rows[:2])
    for detail in reversed(previous['execution_details'])
    for control in reversed(detail.get('execution', {}).get('trace', [])))
np.testing.assert_allclose(robot['eef_xyz_m'], row['request']['robot']['eef_xyz_m'])


def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    if path.suffix == '.png':
        return np.asarray(Image.open(path))
    with np.load(path) as archive:
        return archive[archive.files[0]]


def frame(name):
    return load(directory/name/(f'{step:02d}'+Path(name).suffix))


views = {}
for anchor_id, evidence in row['perception_evidence'].items():
    cameras = {}
    for camera, artifact in evidence.get('sam_mask_files', {}).items():
        assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest() == artifact['sha256']
        source_step = artifact['source_step']
        world = load(directory/(camera+'_world_high.npz')/(f'{source_step:02d}.npz'))
        cameras[camera] = {'source_step': source_step,
            'xyz_world': world[load(artifact['path']).astype(bool)]}
    if cameras:
        views[anchor_id] = cameras
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
       'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
primitive = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
if args.precontact:
    trace = next(detail['execution']['trace'] for previous in reversed(rows[:2])
        for detail in reversed(previous['execution_details']) if detail.get('execution', {}).get('trace'))
    recent = trace[-3:]
    assert len(recent) == 3 and all(a['after'] == b['before'] for a, b in zip(recent, recent[1:]))
    primitive._bounded_motion_samples = list(enumerate([recent[0]['before'], *[r['after'] for r in recent]]))
    primitive._bounded_control_index = 3
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
adapter.p = primitive
adapter.geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
adapter.robot_xml = xml.parent.parent/'robots/panda/robot.xml'
adapter._instance_cache, adapter._screen_cache, adapter._base_geometry = {}, {}, None
adapter._self_filtered_capture = None
adapter.held = adapter.active = adapter.payload_reference = adapter.withdrawal_contact = None
adapter.instance_boundary_evidence, adapter.committed_grasps, adapter.plans = {}, {}, {}
adapter.target_cache, adapter.candidate_diagnostics = {}, []
adapter.record_public_geometry = False
adapter.config = MotionConfig()
entities = {}
for anchor in row['request']['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, step)
adapter.scene = SimpleNamespace(entities=entities, measurement_clouds_by_view=views,
                               measurement_clouds={}, view_axes=([1., 0., 0.], [0., 1., 0.]))
adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step, load=frame)))
adapter._cloud_and_ik()
if args.precontact:
    adapter.active = key
    adapter.committed_grasps[key] = {'plan': {}, 'instance_reference': {
        'xyz_world': load(directory/f'bounded_precontact_{key}_target.npz/00.npz'),
        'source_step': 0}}
    instance = adapter._contact_pixels(key)
else:
    reference_file = max((p for p in (directory/'bounded_payload_reference_robot.json').glob('*.json')
        if int(p.stem) < step), key=lambda p: int(p.stem))
    reference_step = int(reference_file.stem)
    adapter.held = key
    adapter.payload_reference = {
        'target': load(directory/'bounded_payload_reference_target.npz'/f'{reference_step:02d}.npz'),
        'scene': load(directory/'bounded_payload_reference_scene.npz'/f'{reference_step:02d}.npz'),
        'robot': load(reference_file), 'capture_step': reference_step}
    instance = adapter._instance_pixels(key)
tree = cKDTree(instance)
routes = []
for diagnostic in row['candidate_screen_diagnostics']:
    skill = 'lift' if args.precontact else 'carry_to'
    if diagnostic.get('skill') != skill:
        continue
    groups = diagnostic.get('public_scene_collision_points', {})
    points = np.unique([p for values in groups.values() for p in values], axis=0)
    route = adapter._route(skill, diagnostic['parameters'])
    screen = adapter._cloud_and_ik(diagnostic['parameters'].get('target_id', key), contact=args.precontact)
    _, _, _, evidence = SmoothMotion(primitive, screen, adapter.config).prepare(route)
    routes.append({'parameters': diagnostic['parameters'], 'route': route,
        'old_reason': diagnostic['reason'], 'blockers_m': points.tolist(),
        'current_instance_distance_m': tree.query(points)[0].tolist(), 'screen': evidence})
report = {'scope': 'saved public RGB-D, original semantic masks and proprioception; CPU route replay',
    'source': str(args.source), 'job': job, 'row': 2, 'capture_step': step,
    'input_sha256': hashlib.sha256(raw).hexdigest(), 'instance_points': len(instance),
    'source_sha256': {name: hashlib.sha256((args.source/'robots/libero'/name).read_bytes()).hexdigest()
        for name in ('bounded_payload.py', 'bounded_skills.py')},
    'membership': adapter.instance_boundary_evidence[key], 'routes': routes,
    'semantic_temporal_fragments_enabled': not args.without_fragments,
    'controls': 0, 'new_sam_queries': 0, 'private_truth_used': False, 'training': False,
    'limitations': ('Precontact replay reconstructs the final four consecutive public gripper-control samples.'
        if args.precontact else 'No new SAM query; carry reference starts from saved rest pose, not live derivative continuity.')}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'routes': [{k: v for k, v in route.items() if k != 'screen'}
    | {'passed': route['screen']['passed'], 'reason': route['screen']['reason']} for route in routes],
    'membership': [r for r in report['membership'] if 'temporal_prediction_rejected' in r]}))
