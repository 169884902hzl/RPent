"""Compare cached and rebuilt handle membership at an identical public capture."""
# ruff: noqa: E402 -- immutable source and CPU before robot imports
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_276456d_20261018'
sys.path.insert(0,str(source))
import numpy as np
from scipy.spatial import cKDTree
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers, gripper_visual_boxes, remove_current_gripper, remove_visual_robot)
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import separate_target_points

directory = next((root/'results/bounded_skills/feasibility_20261017/job8246_140').glob('*oracle*'))
raw = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
row, key = rows[3], 'e98'
robot = rows[2]['execution_details'][-1]['execution']['trace'][-1]['after']
for name in ('eef_xyz_m','eef_quat_xyzw'):
    np.testing.assert_allclose(robot[name],row['request']['robot'][name],atol=1e-10)
step = row['public_geometry_evidence']['bounded_screen_e98_1_target']['capture_step']
def load(name):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    with np.load(path) as z:
        return z[z.files[0]]
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml),'visual_boxes':gripper_visual_boxes(str(xml))}
hand = gripper_at_measured_fingers(geometry,robot['finger_positions_m'])
cloud = np.concatenate([load(c+'_world_high.npz').reshape(-1,3) for c in ('agentview','wrist')])
cloud,_ = remove_current_gripper(cloud,robot['eef_xyz_m'],robot['eef_quat_xyzw'],hand,robot['gripper_opening_m'])
ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
    robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
cloud,_ = ik.remove_measured_arm(cloud)
cloud,_ = remove_visual_robot(cloud,ik)
plan = copy.deepcopy(next(d['plan'] for d in row['candidate_screen_diagnostics']
    if d.get('stage')=='fixture_contact_plan' and d.get('anchor_id')==key))
contact_robot = rows[2]['execution_details'][-1]['execution']['trace'][-1]['after']
obs = {'robot0_eef_pos':robot['eef_xyz_m'],'robot0_eef_quat':robot['eef_quat_xyzw'],
    'robot0_gripper_qpos':robot['finger_positions_m'],'robot0_joint_pos':robot['joint_positions_rad']}
a = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
a.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:obs))
a.geometry, a.active, a.held = geometry,key,None
a.plans = {key:plan}
a.committed_grasps = {key:{'plan':plan,'contact_robot':contact_robot}}
a.withdrawal_contact = None
a._base_geometry = cloud,ik
a.scene = SimpleNamespace(entities={})
a._instance_pixels = lambda key:np.empty((0,3))
a.instance_boundary_evidence = {}
a.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step,load=load)))
target = a._contact_pixels(key,handle_only=True)
from scipy.spatial.transform import Rotation
import robots.libero.bounded_skills as runtime
original_completion = runtime.complete_cylindrical_contact_surface
old_handle = a._stored_handle_pixels(plan['handle_measurement'], contact_surface=True)
values, axes = np.linalg.eigh(np.cov(old_handle.T))
old_rotation = Rotation.from_quat(contact_robot['eef_quat_xyzw']).as_matrix()
rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
measured_axis = rotation@old_rotation.T@axes[:,-1]
def measured_completion(world, reference, axis):
    return original_completion(world, reference, measured_axis)
runtime.complete_cylindrical_contact_surface = measured_completion
corrected = a._contact_pixels(key,handle_only=True)
runtime.complete_cylindrical_contact_surface = original_completion

old_target, old_scene = load('bounded_screen_e98_1_target.npz'),load('bounded_screen_e98_1_scene.npz')
new_target, new_scene = separate_target_points(np.concatenate([old_target,corrected]),cloud)
block = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill')=='nudge'
    and d['parameters']=={'anchor_id':key,'axis':'y','distance_m':.02})
point = np.asarray(block['public_scene_collision_points']['rightfinger_pad'][0])
report = {'scope':'public saved sensors only,zero controls;test measured 3D handle-axis hypothesis',
    'gpu_used':False,'private_truth_used':False,'training':False,'row':3,'current_measured_axis':measured_axis.tolist(),'axis_eigenvalues':values.tolist(),
    'choices_sha256':hashlib.sha256(raw).hexdigest(),'source':str(source),
    'cached_target_points':len(old_target),'reconstructed_contact_points':len(target),'corrected_contact_points':len(corrected),'original_contact_blocker_distance_m':float(cKDTree(target).query(point)[0]),'corrected_contact_blocker_distance_m':float(cKDTree(corrected).query(point)[0]),'rebuilt_target_points':len(new_target),
    'cached_blocker_target_distance_m':float(cKDTree(old_target).query(point)[0]),
    'rebuilt_blocker_target_distance_m':float(cKDTree(new_target).query(point)[0]),'screens':[]}
goal = {'xyz_m':(np.asarray(robot['eef_xyz_m'])+[0.,.02,0.]).tolist(),'quat_xyzw':robot['eef_quat_xyzw']}
for name,points,contact in (('cached',old_scene,old_target),('rebuilt',new_scene,new_target)):
    screen = PublicRouteScreen(points,hand,ik.with_measured_robot(robot),opening=robot['gripper_opening_m'],
        contact_points=contact,contact_allowed=True,
        initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
    _,_,_,check = SmoothMotion(a.p,screen).prepare([goal])
    report['screens'].append({'method':name,**{k:check[k] for k in (
        'passed','reason','path_min_clearance_m','counts','target_counts') if k in check}})
output = root/'coordination/bounded_skills_20261016/reports/microwave8246_handle_axis_pair_CPU_20261018.json'
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
