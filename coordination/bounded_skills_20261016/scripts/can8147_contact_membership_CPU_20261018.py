"""Locate exact public pixels blocking the saved pre-lift route."""
# ruff: noqa: E402 -- select the recorded immutable source and CPU first
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root / 'source_bounded_9368299_20261018'))
import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_geometry import clean_object_mask

development = 'dev' in sys.argv[1:]
if development:
    geometry_spec = importlib.util.spec_from_file_location('robots.libero.v5_grasp_geometry',
        root / 'results/bounded_skills/feasibility_20261017/preparation/grasp_geometry_semantic_fragments_dev_CPU_20261018.py')
    geometry_module = importlib.util.module_from_spec(geometry_spec)
    sys.modules[geometry_spec.name] = geometry_module
    geometry_spec.loader.exec_module(geometry_module)
    spec = importlib.util.spec_from_file_location('robots.libero.bounded_skills_fused_extent',
        root / 'results/bounded_skills/feasibility_20261017/preparation/bounded_skills_fused_extent_dev_CPU_20261018.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MeasuredSkillAdapter = module.MeasuredSkillAdapter

directory = next((root / 'results/bounded_skills/feasibility_20261017/job8147_21').glob('*oracle*'))
choices = directory / 'choices.jsonl'
rows = [json.loads(line) for line in choices.open()]
row, key = rows[2], 'e35'
robot = rows[1]['execution_details'][-1]['execution']['trace'][-1]['after']
anchor = next(a for a in row['request']['anchors'] if a['id'] == key)
centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
entity = SimpleNamespace(id=key, name=anchor['label'], part_of=None,
    lower=centre-size/2, upper=centre+size/2)


def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    with np.load(path) as archive:
        return archive[archive.files[0]]


views, worlds, masks = {}, {}, {}
step = next(iter(row['public_geometry_evidence'].values()))['capture_step']
for camera, reference in row['perception_evidence'][key]['sam_mask_files'].items():
    world = load(directory/(camera+'_world_high.npz')/(f'{step:02d}.npz'))
    mask = load(reference['path']).astype(bool)
    views[camera] = {'source_step': step, 'xyz_world': world[mask]}
    worlds[camera], masks[camera] = world, mask
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
    'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
primitive = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
adapter.p = primitive
adapter.geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
adapter.robot_xml = xml.parent.parent/'robots/panda/robot.xml'
adapter._instance_cache, adapter._screen_cache, adapter._base_geometry = {}, {}, None
adapter.held = adapter.active = adapter.payload_reference = adapter.withdrawal_contact = None
adapter.instance_boundary_evidence, adapter.committed_grasps, adapter.plans = {}, {}, {}
adapter.record_public_geometry = False
adapter.scene = SimpleNamespace(entities={key: entity}, measurement_clouds_by_view={key: views},
    measurement_clouds={})
adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step,
    load=lambda name: load(directory/name/(f'{step:02d}'+Path(name).suffix)))))
membership_stages = []
if development:
    probe = np.array([-.08876792341470718, -.250413715839386, .07952945679426193])
    original_clean = module.clean_object_mask
    original_cross = module.complete_crossview_boundary
    def membership(world, mask):
        hits = np.isfinite(world).all(axis=2) & (np.linalg.norm(world-probe, axis=2) < 1e-6)
        return {'present': bool(hits.any()), 'member': bool((hits & mask).any())}
    def traced_clean(world, mask, **kwargs):
        result, evidence = original_clean(world, mask, **kwargs)
        membership_stages.append({'operation': 'clean', 'before': membership(world, mask),
            'after': membership(world, result)})
        return result, evidence
    def traced_cross(world, mask, *args, **kwargs):
        result, evidence = original_cross(world, mask, *args, **kwargs)
        membership_stages.append({'operation': 'crossview', 'before': membership(world, mask),
            'after': membership(world, result)})
        return result, evidence
    module.clean_object_mask, module.complete_crossview_boundary = traced_clean, traced_cross
screen = adapter._cloud_and_ik(key, contact=True)
if not development:
    for kind, cloud in (('scene', screen.points), ('target', screen.target)):
        saved = load(row['public_geometry_evidence'][f'bounded_screen_{key}_1_{kind}']['path'])
        np.testing.assert_array_equal(cloud, saved)
point = np.array(robot['eef_xyz_m'])
point[2] += .1
_, _, _, route = SmoothMotion(primitive, screen).prepare([{'xyz_m': point.tolist(),
    'quat_xyzw': robot['eef_quat_xyzw']}])
diagnostic = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'lift')
blockers = np.unique(np.concatenate([points for points in diagnostic['public_scene_collision_points'].values() if points]), axis=0)
records = []
for camera in ('agentview', 'wrist'):
    world = load(directory/(camera+'_world_high.npz')/(f'{step:02d}.npz'))
    flat = world.reshape(-1, 3)
    finite = np.flatnonzero(np.isfinite(flat).all(axis=1))
    distances, near = cKDTree(flat[finite]).query(blockers)
    filtered = adapter._self_filtered_world(world)
    mask = masks.get(camera, np.zeros(world.shape[:2], bool))
    clean, evidence = clean_object_mask(filtered, mask, prior_lower=entity.lower, prior_upper=entity.upper)
    measured = filtered[clean]
    instance = adapter._instance_pixels(key)
    points = []
    for i, distance in enumerate(distances):
        pixel = int(finite[near[i]])
        y, x = divmod(pixel, world.shape[1])
        points.append({'xyz_m': blockers[i].tolist(), 'pixel_yx': [y, x],
            'world_residual_m': float(distance), 'original_mask': bool(mask[y, x]),
            'clean_mask': bool(clean[y, x]), 'self_filtered': bool(np.isfinite(filtered[y, x]).all()),
            'within_clean_extent': bool(len(measured) and (blockers[i] >= measured.min(0)).all()
                and (blockers[i] <= measured.max(0)).all()),
            'nearest_clean_pixel_m': float(cKDTree(measured).query(blockers[i])[0]) if len(measured) else None,
            'nearest_instance_pixel_m': float(cKDTree(instance).query(blockers[i])[0])})
        if development:
            valid = np.isfinite(world).all(axis=2)
            pixels = np.flatnonzero(valid)
            present = cKDTree(instance).query(world[valid],
                distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
            supported = world.reshape(-1, 3)[pixels[present]]
            distances, neighbours = cKDTree(supported).query(blockers[i], k=8)
            patch = supported[neighbours]
            mean = patch.mean(0)
            _, spread, axes = np.linalg.svd(patch-mean)
            points[-1]['current_plane'] = {'nearest8_distances_m': distances.tolist(),
                'singular_values': spread.tolist(),
                'fit_max_residual_m': float(np.abs((patch-mean) @ axes[-1]).max()),
                'query_plane_residual_m': float(abs((blockers[i]-mean) @ axes[-1]))}
    records.append({'camera': camera, 'points': points, 'clean_component': evidence})
report = {'scope': 'exact saved public RGB-D reconstruction; zero controls; no private truth',
    'training': False, 'gpu_used': False,
    'input': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest(), 'row': 2},
    'screen_exactly_reproduced': not development, 'development_module': development,
    'route': {k:route[k] for k in ('passed', 'reason', 'collision', 'ik_reachable', 'path_min_clearance_m',
        'at', 'counts', 'target_counts', 'public_scene_collision_points') if k in route},
    'membership_stages': membership_stages,
    'scene_points': len(screen.points), 'target_points': len(screen.target),
    'boundary': adapter.instance_boundary_evidence, 'blocker_pixels': records}
suffix = '_dev' if development else ''
output = root/f'coordination/bounded_skills_20261016/reports/can8147_contact_membership_CPU_20261018{suffix}.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'scene_points': len(screen.points), 'target_points': len(screen.target), 'route': report['route'],
    'blocker_pixels': [{k:v for k,v in r.items() if k != 'clean_component'} for r in records]}, indent=2))
