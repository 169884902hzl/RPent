"""Trace exact saved public cup pixels through current membership stages."""
# ruff: noqa: E402 -- select immutable source and CPU before imports
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_11ec9aa_20261018'
sys.path.insert(0, str(source))
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from types import SimpleNamespace
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_state import Entity
import robots.libero.bounded_skills as module
import robots.libero.bounded_payload as payload

base = root/'coordination/bounded_skills_20261016'
directory = next((root/'results/bounded_skills/feasibility_20261017/job8249_60').glob('*oracle*'))
captured = (directory/'choices.jsonl').read_bytes().splitlines()[:13]
rows = [json.loads(line) for line in captured]
row, key = rows[12], 'e6'
robot = next(control['after'] for old in reversed(rows[:12])
    for detail in reversed(old['execution_details'])
    for control in reversed(detail['execution'].get('trace', [])))
for name in ('eef_xyz_m', 'eef_quat_xyzw'):
    np.testing.assert_allclose(robot[name], row['request']['robot'][name], atol=1e-10)
step = row['public_geometry_evidence']['bounded_screen_e6_1_scene']['capture_step']
def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    if path.suffix == '.png':
        return np.asarray(Image.open(path))
    with np.load(path) as z:
        return z[z.files[0]]
def frame(name):
    return load(directory/name/(f'{step:02d}'+Path(name).suffix))
views = {}
for camera, ref in row['perception_evidence'][key]['sam_mask_files'].items():
    assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() == ref['sha256']
    world = frame(camera+'_world_high.npz')
    mask = load(ref['path']).astype(bool)
    views[camera] = {'source_step': step, 'xyz_world': world[mask]}
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
    'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
a = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
a.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
a.geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
a.robot_xml = xml.parent.parent/'robots/panda/robot.xml'
a._instance_cache, a._screen_cache, a._base_geometry = {}, {}, None
a.held = a.active = a.payload_reference = a.withdrawal_contact = None
a.instance_boundary_evidence, a.committed_grasps, a.plans = {}, {}, {}
a.record_public_geometry = False
entities = {}
for anchor in row['request']['anchors']:
    centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
    entities[anchor['id']] = Entity(anchor['id'], anchor['label'], tuple(centre),
        tuple(centre-size/2), tuple(centre+size/2), True, step)
a.scene = SimpleNamespace(entities=entities, measurement_clouds_by_view={key: views}, measurement_clouds={})
a.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step, load=frame)))
a._cloud_and_ik()
a.held = key
a.payload_reference = {'target': load(directory/'bounded_payload_reference_target.npz/11.npz'),
    'scene': load(directory/'bounded_payload_reference_scene.npz/11.npz'),
    'robot': load(directory/'bounded_payload_reference_robot.json/11.json'), 'capture_step': 11}
blockers = np.unique(np.array([d['obstacle_point'] for d in row['candidate_screen_diagnostics']
    if d.get('skill') == 'carry_to' and d.get('obstacle_point')]), axis=0)
stages = []
def trace(name, original):
    def wrapped(world, *args, **kwargs):
        mask, evidence = original(world, *args, **kwargs)
        pixels = np.asarray(world)[mask & np.isfinite(world).all(axis=-1)]
        stages.append({'function': name, 'shape': list(np.asarray(world).shape),
            'nearest_member_m': cKDTree(pixels).query(blockers)[0].tolist() if len(pixels) else [],
            'member_pixels': len(pixels), 'evidence': evidence})
        return mask, evidence
    return wrapped
for name in ('clean_object_mask', 'complete_instance_boundary', 'complete_planar_boundary',
             'complete_sparse_instance_boundary', 'complete_crossview_boundary', 'retain_crossview_semantic_fragments'):
    setattr(module, name, trace(name, getattr(module, name)))
for name in ('complete_moving_boundary', 'complete_spatial_payload_component'):
    setattr(payload, name, trace(name, getattr(payload, name)))
def saved_guided(world, semantic, camera, entity, current):
    evidence = next(e for e in row['instance_boundary_evidence'][key]
        if e.get('source') == 'current_measured_instance_interior_point_sam' and e['camera'] == camera)
    ref = evidence['artifact']
    assert hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() == ref['sha256']
    return load(ref['path']), copy.deepcopy(evidence)
# Exact recorded point-query output: no synthesized service responses or new calls.
a._guided_payload_pixels = saved_guided
instance = a._instance_pixels(key)
patches = []
tree = cKDTree(instance)
static = cKDTree(a.payload_reference['scene'])
for camera in ('agentview', 'wrist'):
    world = a._self_filtered_world(frame(camera+'_world_high.npz'))
    rgb = frame(camera+'_high.png')
    semantic = load(row['perception_evidence'][key]['sam_mask_files'][camera]['path']).astype(bool)
    owned = np.zeros(world.shape[:2], bool)
    ids = np.flatnonzero(np.isfinite(world).all(2))
    owned.flat[ids] = tree.query(world.reshape(-1, 3)[ids], distance_upper_bound=1.00001e-6)[0] <= 1e-6
    for point in blockers:
        raw = frame(camera+'_world_high.npz')
        distance = np.linalg.norm(raw-point, axis=2)
        y, x = np.unravel_index(np.argmin(distance), distance.shape)
        if distance[y, x] > 1e-6:
            continue
        region = np.s_[y-4:y+5, x-4:x+5]
        local = world[region]
        patches.append({'camera': camera, 'pixel_xy': [int(x), int(y)], 'point_m': point.tolist(),
            'prelift_static_nearest_m': float(static.query(point)[0]),
            'nearest_member_m': float(tree.query(point)[0]),
            'inside_final_extent': bool(((point >= instance.min(0)) & (point <= instance.max(0))).all()),
            'owned': owned[region].astype(int).tolist(), 'semantic': semantic[region].astype(int).tolist(),
            'finite': np.isfinite(local).all(2).astype(int).tolist(),
            'rgb': rgb[region].tolist(), 'xyz_world': local.tolist(),
            'distance_from_point_m': np.linalg.norm(local-point, axis=2).tolist()})
report = {'scope': 'exact saved public RGB-D, robot feedback and recorded real point-query clouds; zero controls',
    'source': str(source), 'private_truth_used': False, 'gpu_used': False, 'training': False,
    'choices_prefix_sha256': hashlib.sha256(b'\n'.join(captured)).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'blockers': blockers.tolist(), 'instance_points': len(instance),
    'nearest_member_m': tree.query(blockers)[0].tolist(),
    'stages': stages, 'patches': patches, 'boundary': a.instance_boundary_evidence[key]}
output = base/'reports/cup8249_membership_stages_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: report[k] for k in ('instance_points', 'nearest_member_m', 'patches')}))
