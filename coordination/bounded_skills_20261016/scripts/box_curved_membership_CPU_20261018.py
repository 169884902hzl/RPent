"""Test measured curved-surface membership on saved public box RGB-D only."""
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
parser.add_argument('--queries-only', action='store_true')
parser.add_argument('--sam-report', type=Path)
parser.add_argument('--precontact', action='store_true')
parser.add_argument('--precontact-screen', action='store_true')
parser.add_argument('--precontact-exact', action='store_true')
parser.add_argument('--register-precontact', action='store_true')
parser.add_argument('--working-adapter', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.bounded_motion import MotionConfig, SmoothMotion
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_geometry import (
    complete_cylindrical_contact_surface,
    complete_contact_surface,
    complete_instance_boundary,
    complete_planar_boundary,
    clean_object_mask,
)
from robots.libero.v5_state import Entity

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
             for control in reversed(detail['execution'].get('trace', [])))
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
if args.precontact or args.precontact_screen or args.precontact_exact:
    earlier = rows[0]
    anchor = next(a for a in earlier['request']['anchors'] if a['id'] == key)
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    reference, references = [], []
    for camera, artifact in earlier['perception_evidence'][key]['sam_mask_files'].items():
        assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest() == artifact['sha256']
        old_step = artifact['source_step']
        world = load(directory/(camera+'_world_high.npz')/(f'{old_step:02d}.npz'))
        clean, evidence = clean_object_mask(world, load(artifact['path']).astype(bool),
            prior_lower=centre-size/2, prior_upper=centre+size/2)
        reference.append(world[clean])
        references.append({'camera': camera, 'capture_step': old_step, **evidence})
    reference = np.concatenate(reference)
    if args.precontact_screen:
        artifact = earlier['public_geometry_evidence'][f'bounded_screen_{key}_1_target']
        assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest() == artifact['sha256']
        reference = load(artifact['path'])
        references = [artifact]
    if args.precontact_exact:
        old_step = earlier['public_geometry_evidence'][f'bounded_screen_{key}_1_target']['capture_step']
        old_robot = rows[0]['execution_details'][0]['execution']['trace'][0]['before']
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
        references = [{'source': 'exact_rebuilt_public_instance_pixels', 'capture_step': old_step,
            'points': len(reference), 'boundary': old.instance_boundary_evidence[key]}]
    registration = None
    if args.register_precontact:
        from robots.libero.bounded_payload import _surface_registration
        reference, registration = _surface_registration(reference, instance)
    current, curved, cameras = [instance], [instance], []
    _, axes = np.linalg.eigh(np.cov(reference.T))
    for camera in ('agentview', 'wrist'):
        world = adapter._self_filtered_world(frame(camera+'_world_high.npz'))
        mask, evidence = complete_contact_surface(world, reference, current_boundary=True)
        current.append(world[mask])
        cylinder, fit = complete_cylindrical_contact_surface(world, reference, axes[:, -1])
        extent = ((world >= reference.min(0)-.001).all(axis=2)
            & (world <= reference.max(0)+.001).all(axis=2))
        curved.append(world[(mask | cylinder) & extent])
        cameras.append({'camera': camera, 'cylinder': fit, **evidence})
    distances = cKDTree(np.concatenate(current)).query(blockers)[0]
    curved_distances = cKDTree(np.concatenate(curved)).query(blockers)[0]
    adapter.config = MotionConfig()
    tail = [control['after'] for old in rows[:args.row] for detail in old['execution_details']
            for control in detail['execution'].get('trace', [])][-4:]
    adapter.p._bounded_motion_samples = list(enumerate(tail))
    adapter.p._bounded_control_index = len(tail)-1
    adapter.active = key
    waypoint = {'xyz_m': (np.asarray(robot['eef_xyz_m'])+[0., 0., .1]).tolist(),
                'quat_xyzw': robot['eef_quat_xyzw']}
    stages = []
    for name, points in [('baseline', instance), ('precontact_curved', np.concatenate(curved))]:
        if name == 'precontact_curved' and args.working_adapter:
            spec = importlib.util.spec_from_file_location('precontact_candidate_adapter', args.working_adapter)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            adapter.__class__ = module.MeasuredSkillAdapter
            adapter.committed_grasps[key] = {'plan': {}, 'instance_reference': {
                'xyz_world': reference, 'source_step': 0}}
            adapter._instance_cache.clear()
            points = instance
            name = 'runtime_precontact_surface'
            if args.register_precontact:
                name += '_prototype_registered_reference'
        adapter._instance_cache[key] = points
        adapter._screen_cache.clear()
        screen = adapter._cloud_and_ik(key, contact=True)
        _, _, _, evidence = SmoothMotion(adapter.p, screen, adapter.config).prepare([waypoint])
        stages.append({'name': name, 'route_screen': evidence})
    result = {'scope': 'saved current public RGB-D matches cleaned precontact target surface; no controls',
        'private_truth_used': False, 'controls': 0, 'training': False, 'gpu_used': False,
        'job': args.job, 'row': args.row, 'capture_step': step,
        'reference_points': len(reference), 'reference': references, 'cameras': cameras,
        'prototype_reference_registration': registration,
        'blocker_distances_m': distances.tolist(), 'recovered_blockers': int((distances < 1e-6).sum()),
        'curved_reference_distances_m': curved_distances.tolist(),
        'curved_reference_recovered': int((curved_distances < 1e-6).sum()),
        'route_stages': stages,
        'working_adapter_sha256': hashlib.sha256(args.working_adapter.read_bytes()).hexdigest() if args.working_adapter else None,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['job', 'recovered_blockers',
        'curved_reference_recovered', 'blocker_distances_m', 'curved_reference_distances_m']}))
    print(json.dumps([{'stage': s['name'], 'passed': s['route_screen']['passed'],
        'reason': s['route_screen']['reason']} for s in stages]))
    sys.exit(0)
if args.sam_report:
    report = json.loads(args.sam_report.read_text())
    assert report['private_truth_used'] is False
    lower, upper = instance.min(0), instance.max(0)
    measured, restricted, cameras = [instance], [instance], []
    for result in report['results']:
        camera = result['camera']
        assert result['found']
        assert hashlib.sha256(Path(result['mask']).read_bytes()).hexdigest() == result['sha256']
        with np.load(result['mask']) as archive:
            raw = archive['mask']
        point = tuple(result['query']['point'])
        assert raw[point]
        world = adapter._self_filtered_world(frame(camera+'_world_high.npz'))
        cleaned, evidence = clean_object_mask(world, raw,
            prior_lower=entities[key].lower, prior_upper=entities[key].upper)
        assert cleaned[point], 'The new mask lost its measured identity seed'
        measured.append(world[cleaned])
        valid = ((world >= lower).all(axis=2) & (world <= upper).all(axis=2))
        restricted.append(world[raw & valid])
        cameras.append({'camera': camera, 'raw_pixels': int(raw.sum()),
            'cleaned_pixels': int(cleaned.sum()), 'cleanup': evidence,
            'restricted_pixels': int((raw & valid).sum())})
    stages = []
    adapter.config = MotionConfig()
    tail = [control['after'] for old in rows[:args.row] for detail in old['execution_details']
            for control in detail['execution'].get('trace', [])][-4:]
    adapter.p._bounded_motion_samples = list(enumerate(tail))
    adapter.p._bounded_control_index = len(tail)-1
    adapter.active = key
    waypoint = {'xyz_m': (np.asarray(robot['eef_xyz_m'])+[0., 0., .1]).tolist(),
                'quat_xyzw': robot['eef_quat_xyzw']}
    for name, points in [('baseline', instance), ('guided_with_old_extent', np.concatenate(restricted)),
                         ('guided_depth_component', np.concatenate(measured))]:
        adapter._instance_cache[key] = points
        adapter._screen_cache.clear()
        screen = adapter._cloud_and_ik(key, contact=True)
        _, _, _, evidence = SmoothMotion(adapter.p, screen, adapter.config).prepare([waypoint])
        distances = cKDTree(points).query(blockers)[0]
        stages.append({'name': name, 'member_pixels': len(points),
            'recovered_blockers': int((distances < 1e-6).sum()), 'blocker_distances_m': distances.tolist(),
            'route_screen': evidence})
    output = {'scope': 'saved public RGB-D and point-prompt SAM; paired complete lift-route screening only',
        'private_truth_used': False, 'controls': 0, 'training': False,
        'job': args.job, 'row': args.row, 'capture_step': step, 'anchor_id': key,
        'source': str(args.source), 'sam_report': str(args.sam_report), 'stages': stages,
        'cameras': cameras, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'stages': [
        {'name': s['name'], 'recovered_blockers': s['recovered_blockers'],
         'passed': s['route_screen']['passed'], 'reason': s['route_screen']['reason']} for s in stages]}))
    sys.exit(0)
if args.queries_only:
    from scipy.ndimage import distance_transform_edt

    queries = []
    lower, upper = instance.min(0), instance.max(0)
    for camera, artifact in row['perception_evidence'][key]['sam_mask_files'].items():
        world = adapter._self_filtered_world(frame(camera+'_world_high.npz'))
        valid = (np.isfinite(world).all(axis=2)
            & (world >= lower).all(axis=2) & (world <= upper).all(axis=2))
        interior = load(artifact['path']).astype(bool) & valid
        assert interior.any(), camera
        point = list(map(int, np.unravel_index(
            np.argmax(distance_transform_edt(interior)), interior.shape)))
        image = directory/(camera+'_high.png')/(f'{step:02d}.png')
        queries.append({'camera': camera, 'point': point, 'image': str(image),
            'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'public_seed_m': world[tuple(point)].tolist()})
    report = {'scope': 'maximum interior-distance point of each current public instance mask; '
        'same deterministic prompt as _guided_payload_pixels; no blocker or private label selects a point',
        'private_truth_used': False, 'controls': 0, 'training': False, 'gpu_used': False,
        'job': args.job, 'row': args.row, 'capture_step': step,
        'surface_bounds_m': [lower.tolist(), upper.tolist()],
        'queries': queries, 'source': str(args.source),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    sys.exit(0)
values, axes = np.linalg.eigh(np.cov(instance.T))
trials = []
for index in range(3):
    references, continued_references, cameras = [instance], [instance], []
    for camera in ('agentview', 'wrist'):
        world = adapter._self_filtered_world(frame(camera+'_world_high.npz'))
        mask, evidence = complete_cylindrical_contact_surface(world, instance, axes[:, index])
        points = world[mask]
        references.append(points)
        continued, linear = complete_instance_boundary(world, mask)
        continued, planar = complete_planar_boundary(world, continued)
        continued_references.append(world[continued])
        valid = np.isfinite(world).all(axis=2)
        camera_tree = cKDTree(world[valid])
        pixel_dist, pixel_index = camera_tree.query(blockers)
        ids = np.flatnonzero(valid)
        recovered = (pixel_dist < 1e-6) & mask.ravel()[ids[pixel_index]]
        cameras.append({'camera': camera, 'matched_blockers': recovered.tolist(),
            'continuation': {'linear': linear, 'planar': planar}, **evidence})
    distances = cKDTree(np.concatenate(references)).query(blockers)[0]
    continued_distances = cKDTree(np.concatenate(continued_references)).query(blockers)[0]
    trials.append({'axis': axes[:, index].tolist(), 'axis_variance_m2': float(values[index]),
        'blocker_distances_after_m': distances.tolist(), 'recovered_blockers': int((distances < 1e-6).sum()),
        'continuation_distances_m': continued_distances.tolist(),
        'continuation_recovered': int((continued_distances < 1e-6).sum()), 'cameras': cameras})
report = {'scope': 'saved public RGB-D curved-surface hypothesis only; no route or physical result',
    'private_truth_used': False, 'controls': 0, 'training': False, 'gpu_used': False,
    'job': args.job, 'row': args.row, 'capture_step': step, 'anchor_id': key,
    'source': str(args.source), 'instance_points': len(instance),
    'prefix_sha256': hashlib.sha256(b'\n'.join(prefix[:args.row+1])).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'blockers_m': blockers.tolist(), 'baseline_distances_m': baseline_dist.tolist(), 'trials': trials}
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(args.output), 'baseline_unowned': int((baseline_dist > 1e-6).sum()),
    'trials': [{k: t[k] for k in ('axis', 'recovered_blockers', 'continuation_recovered')}
               for t in trials]}))
