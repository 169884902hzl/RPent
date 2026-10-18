"""Rebuild measured handle membership after the recorded zero-step rejection."""
import copy
import argparse
import importlib.util
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_self_filter_20261018_b6cf6d0'
parser = argparse.ArgumentParser()
parser.add_argument('--rolling', action='store_true')
parser.add_argument('--candidate-file', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial import cKDTree
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers, gripper_visual_boxes, remove_current_gripper, remove_visual_robot)
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
if args.candidate_file:
    spec = importlib.util.spec_from_file_location('candidate_bounded_skills', args.candidate_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MeasuredSkillAdapter = module.MeasuredSkillAdapter

directory = root/'results/bounded_skills/feasibility_20261017/job8862_140/microwave_open_libero_90_t35_s0_oracle_k4'
raw = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines()]
row, key = rows[3], 'e98'
last = [d['execution'] for d in rows[2]['execution_details'] if d.get('execution', {}).get('trace')][-1]
robot = last['trace'][-1]['after']
for name in ('eef_xyz_m', 'eef_quat_xyzw'):
    np.testing.assert_allclose(robot[name], row['request']['robot'][name], atol=1e-10)
rejection = rows[2]['receipts'][-1]
assert rejection['skill'] == 'nudge' and rejection['steps_used'] == 0 and rejection['outcome'] == 'failure'
contact_robot = rows[0]['execution_details'][-1]['execution']['trace'][-1]['after']
plan = copy.deepcopy(next(d['plan'] for d in rows[0]['candidate_screen_diagnostics']
    if d.get('stage') == 'fixture_contact_plan' and d.get('anchor_id') == key))
step = row['public_geometry_evidence']['bounded_screen_e98_1_target']['capture_step']
inputs = {}
def load(name):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    inputs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    with np.load(path) as stored:
        return stored[stored.files[0]]
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
hand = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
    robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
    'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
a = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
a.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs, terminated=False))
a.record_public_geometry = False
a.geometry, a.active, a.held = geometry, key, None
a.plans = {key: plan}
a.committed_grasps = {key: {'plan': plan, 'contact_robot': contact_robot}}
a.withdrawal_contact = None
a._self_filtered_capture = None
a.scene = SimpleNamespace(entities={})
a._instance_pixels = lambda key: np.empty((0, 3))
a.instance_boundary_evidence = {}
a._instance_cache = {}
a.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step, load=load)))
cloud = np.concatenate([load(camera+'_world_high.npz').reshape(-1, 3) for camera in ('agentview', 'wrist')])
cloud = cloud[np.isfinite(cloud).all(axis=1)]
cloud, _ = remove_current_gripper(cloud, robot['eef_xyz_m'], robot['eef_quat_xyzw'], hand, robot['gripper_opening_m'])
cloud, _ = ik.remove_measured_arm(cloud)
cloud, _ = remove_visual_robot(cloud, ik)
a._base_geometry = cloud, ik
rolling = []
if args.rolling:
    captures = {3: contact_robot}
    for r in rows[:3]:
        details = {d['candidate_id']: d['execution'] for d in r['execution_details'] if 'candidate_id' in d}
        for receipt in r['receipts']:
            trace = details[receipt['candidate_id']].get('trace', [])
            if trace:
                capture = max(e['capture_step'] for e in receipt['evidence'])
                captures[capture] = trace[-1]['after']
    captures[7] = robot
    original_stored = a._stored_handle_pixels
    a._stored_handle_pixels = lambda m, **kw: (m['_public_points'] if '_public_points' in m
        else original_stored(m, **kw))
    for frame in (3, 4, 5, 6, 7):
        step, robot = frame, captures[frame]
        obs.update(robot0_eef_pos=robot['eef_xyz_m'], robot0_eef_quat=robot['eef_quat_xyzw'],
            robot0_gripper_qpos=robot['finger_positions_m'], robot0_joint_pos=robot['joint_positions_rad'])
        a.ex.toolkit._state.latest_step = step
        hand = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
        ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
            robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
        cloud = np.concatenate([load(camera+'_world_high.npz').reshape(-1, 3) for camera in ('agentview', 'wrist')])
        cloud = cloud[np.isfinite(cloud).all(axis=1)]
        cloud, _ = remove_current_gripper(cloud, robot['eef_xyz_m'], robot['eef_quat_xyzw'], hand, robot['gripper_opening_m'])
        cloud, _ = ik.remove_measured_arm(cloud)
        cloud, _ = remove_visual_robot(cloud, ik)
        a._base_geometry, a._self_filtered_capture = (cloud, ik), None
        recovered = a._contact_pixels(key, handle_only=True)
        recovered = np.unique(recovered, axis=0)
        rolling.append(dict(capture_step=frame, measured_pixels=len(recovered),
            evidence=copy.deepcopy(a.instance_boundary_evidence)))
        a.instance_boundary_evidence.clear()
        if len(recovered) >= 40 and frame < 7 and args.candidate_file:
            a._cloud_and_ik = lambda *args, **kwargs: None  # Already built above from this exact capture.
            a._update_contact_surface_reference(key)
        elif len(recovered) >= 40 and frame < 7:
            m = copy.deepcopy(plan['handle_measurement'])
            m.update(source_step=frame, _public_points=recovered)
            plan = {**plan, 'handle_measurement': m}
            a.plans = {key: plan}
            a.committed_grasps = {key: {'plan': plan, 'contact_robot': robot}}
else:
    recovered = a._contact_pixels(key, handle_only=True)
target, scene = load('bounded_screen_e98_1_target.npz'), load('bounded_screen_e98_1_scene.npz')
member = cKDTree(recovered).query(scene, distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
screens = []
for label, points, contact in (('commit_erased', scene, target),
        ('commit_retained', scene[~member], np.concatenate([target, recovered]))):
    for offset in ([0., .01, 0.], [0., .02, 0.], [0., 0., .04], [.04, 0., 0.], [-.04, 0., 0.], [0., -.04, 0.]):
        screen = PublicRouteScreen(points, hand, ik.with_measured_robot(robot),
            opening=robot['gripper_opening_m'], contact_points=contact, contact_allowed=True,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']})
        goal = {'xyz_m': (np.asarray(robot['eef_xyz_m'])+offset).tolist(), 'quat_xyzw': robot['eef_quat_xyzw']}
        _, _, _, evidence = SmoothMotion(a.p, screen).prepare([goal])
        screens.append(dict(method=label, offset_m=offset, **{k: evidence.get(k) for k in (
            'passed', 'reason', 'path_min_clearance_m', 'counts', 'target_counts',
            'public_scene_collision_points', 'public_target_collision_points')}))
report = dict(source=str(source), choices_sha256=hashlib.sha256(raw).hexdigest(), row_index=3,
    inputs=inputs, previous_rejection=rejection, committed_reference_row_index=0, recovered_handle_pixels=len(recovered),
    current_scene_points_reclassified_as_handle=int(member.sum()), screens=screens,
    instance_boundary_evidence=a.instance_boundary_evidence, rolling_captures=rolling, controls=0, gpu_used=False,
    private_truth_used=False, training=False, confirmation=False,
    scope='same public saved state; original committed handle retained after zero-step rejection; no task execution',
    candidate_file=({'path': str(args.candidate_file),
        'sha256': hashlib.sha256(args.candidate_file.read_bytes()).hexdigest()} if args.candidate_file else None),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
suffix = '_rolling' if args.rolling else ''
suffix += '_runtime' if args.candidate_file else ''
output=root/f'coordination/bounded_skills_20261016/reports/microwave8862_contact_commit_CPU_20261018{suffix}.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(output), recovered_handle_pixels=len(recovered),
    reclassified_scene_points=int(member.sum()), screens=[{k: s[k] for k in
        ('method', 'offset_m', 'passed', 'reason', 'counts', 'target_counts')} for s in screens])))
