"""Trace current public cup membership through each geometric cleanup stage."""
# ruff: noqa: E402 -- choose immutable source and CPU before imports
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = 'bc160ff'
sys.path.insert(0, str(root/f'source_bounded_{source}_20261018'))
import numpy as np
from scipy.spatial import cKDTree
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8158_60').glob('*oracle*'))
choices = directory/'choices.jsonl'
rows = [json.loads(line) for line in choices.open()]
row, key = rows[16], 'e6'
robot = rows[15]['execution_details'][-1]['execution']['trace'][-1]['after']
for name in ('eef_xyz_m', 'eef_quat_xyzw'):
    np.testing.assert_allclose(robot[name], row['request']['robot'][name], atol=1e-10)
anchor = next(a for a in row['request']['anchors'] if a['id'] == key)
centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
entity = SimpleNamespace(id=key, name=anchor['label'], part_of=None,
    lower=centre-size/2, upper=centre+size/2)
def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    with np.load(path) as z:
        return z[z.files[0]]
views = {}
step = row['public_geometry_evidence']['bounded_screen_e6_1_scene']['capture_step']
for camera, ref in row['perception_evidence'][key]['sam_mask_files'].items():
    world = load(directory/(camera+'_world_high.npz')/(f'{step:02d}.npz'))
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
a.scene = SimpleNamespace(entities={key: entity}, measurement_clouds_by_view={key: views}, measurement_clouds={})
a.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step,
    load=lambda name: load(directory/name/(f'{step:02d}'+Path(name).suffix)))))
block = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'carry_to'
    and d.get('parameters', {}).get('target_id') == 'e99')
point = np.asarray(block['obstacle_point'])
stages = []
import robots.libero.bounded_skills as module
for name in ('clean_object_mask', 'complete_instance_boundary', 'complete_planar_boundary',
             'complete_sparse_instance_boundary', 'complete_crossview_boundary', 'retain_crossview_semantic_fragments'):
    original = getattr(module, name)
    def traced(world, *args, _name=name, _original=original, **kwargs):
        mask, evidence = _original(world, *args, **kwargs)
        pixels = np.asarray(world)[mask & np.isfinite(world).all(axis=2)]
        valid = np.asarray(world)[np.isfinite(world).all(axis=2)]
        stages.append({'function':_name, 'view_nearest_blocker_m':float(cKDTree(valid).query(point)[0]),
            'nearest_member_m':float(cKDTree(pixels).query(point)[0]) if len(pixels) else None,
            'member_pixels':len(pixels)})
        return mask, evidence
    setattr(module, name, traced)
instance = a._instance_pixels(key)
blockers = np.unique(np.array([d['obstacle_point'] for d in row['candidate_screen_diagnostics']
    if d.get('skill') == 'carry_to' and d.get('obstacle_point')]), axis=0)
report = {'scope': 'current RGB-D membership only; temporal payload path deliberately not reconstructed',
    'source': source, 'row':16, 'private_truth_used':False, 'gpu_used':False, 'training':False,
    'choices_sha256':hashlib.sha256(choices.read_bytes()).hexdigest(),
    'point_count':len(instance), 'blockers':blockers.tolist(),
    'nearest_instance_m':cKDTree(instance).query(blockers)[0].tolist(),
    'stages':stages, 'boundary':a.instance_boundary_evidence}
p = root/'coordination/bounded_skills_20261016/reports/cup8158_current_membership_stages_CPU_20261018.json'
p.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='boundary'}),flush=True)
