"""Pair tracked-handle extents on exact saved public RGB-D and robot sensors."""
# ruff: noqa: E402 -- select source and CPU before robot imports
import hashlib
import importlib.util
import json
import os
import sys
import copy
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_bc160ff_20261018'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial import cKDTree
from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers, gripper_visual_boxes, remove_current_gripper, remove_visual_robot)
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.bounded_payload import contact_axis_registration
from robots.libero.v5_grasp_geometry import clean_object_mask

revision = 'drawer8145'
module_path = source/'robots/libero/bounded_skills.py'
spec = importlib.util.spec_from_file_location('robots.libero.bounded_skills_handle_pair', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
xml = root / '.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
results = []

for task, anchor, close_row, indices in ((100, 'e54', 1, (2, 3, 4, 5)),):
    directory = next((root / f'results/bounded_skills/feasibility_20261017/job8145_{task}').glob('*oracle*'))
    choices = directory / 'choices.jsonl'
    rows = [json.loads(line) for line in choices.open()]
    contact_robot = rows[close_row]['execution_details'][0]['execution']['trace'][-1]['after']

    def load(name, step):
        path = directory / name / (f'{step:02d}' + Path(name).suffix)
        with np.load(path) as archive:
            return archive[archive.files[0]]

    def public_scene(robot, step):
        cloud = np.concatenate([load(camera+'_world_high.npz', step).reshape(-1, 3)
            for camera in ('agentview', 'wrist')])
        hand = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
        cloud, _ = remove_current_gripper(cloud, robot['eef_xyz_m'], robot['eef_quat_xyzw'],
            hand, robot['gripper_opening_m'])
        ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
            robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
        cloud, _ = ik.remove_measured_arm(cloud)
        cloud, _ = remove_visual_robot(cloud, ik)
        return cloud, ik

    for index in indices:
        row = rows[index]
        step = row['public_geometry_evidence'][f'bounded_screen_{anchor}_1_target']['capture_step']
        before = row['execution_details'][0]['execution']['trace'][0]['before']
        after = row['execution_details'][0]['execution']['trace'][-1]['after']
        cloud, ik = public_scene(before, step)
        after_cloud, _ = public_scene(after, step+1)
        plan = copy.deepcopy(next(d['plan'] for d in row['candidate_screen_diagnostics']
            if d.get('stage') == 'fixture_contact_plan' and d.get('anchor_id') == anchor))
        adapter = module.MeasuredSkillAdapter.__new__(module.MeasuredSkillAdapter)
        obs = {'robot0_eef_pos': before['eef_xyz_m'], 'robot0_eef_quat': before['eef_quat_xyzw'],
            'robot0_gripper_qpos': before['finger_positions_m'], 'robot0_joint_pos': before['joint_positions_rad']}
        adapter.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
        adapter.geometry = geometry
        adapter.active, adapter.held = anchor, None
        adapter.plans = {anchor: plan}
        adapter.committed_grasps = {anchor: {'plan': plan, 'contact_robot': contact_robot}}
        adapter.withdrawal_contact = None
        adapter._base_geometry = cloud, ik
        adapter.scene = SimpleNamespace(entities={})
        adapter._instance_pixels = lambda key: np.empty((0, 3))
        adapter.instance_boundary_evidence = {}
        adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(
            latest_step=step, load=lambda name: load(name, step))))
        current = adapter._contact_pixels(anchor, handle_only=True)
        old = load(f'bounded_contact_{anchor}_reference.npz', step)
        command = row['execution_details'][0]['execution']['public_contact_motion']
        selected = next(c for c in row['request']['candidates']
            if c['id'] == row['decision']['candidate_ids'][0])
        axis, distance = selected['parameters']['axis'], selected['parameters']['distance_m']
        fit = contact_axis_registration(current, after_cloud, 'xyz'.index(axis), distance)
        record = {'job': f'8145_{task}', 'row': index, 'capture_step': step,
            'old_reference_points': len(old), 'new_reference_points': len(current),
            'old_reference_median_m': np.median(old, axis=0).tolist(),
            'new_reference_median_m': np.median(current, axis=0).tolist() if len(current) else None,
            'old_reference_bounds_m': np.quantile(old, [.02, .98], axis=0).tolist(),
            'new_reference_bounds_m': np.quantile(current, [.02, .98], axis=0).tolist() if len(current) else None,
            'old_axis_fit': command['surface_registration'], 'new_axis_fit': fit,
            'physical_execution_replayed': False,
            'choices': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest()},
            'new_evidence': adapter.instance_boundary_evidence.get(anchor, [])}
        results.append(record)
        print({k: record[k] for k in ('job', 'row', 'old_reference_points', 'new_reference_points',
            'old_reference_median_m', 'new_reference_median_m')},
            'old_interval', (command['surface_registration'] or {}).get('compatible_axis_interval_m'),
            'new_interval', fit.get('compatible_axis_interval_m'), flush=True)
report = {'scope': 'paired saved public handle reference and progress measurement; zero controls; no task-success claim',
    'training': False, 'gpu_used': False, 'private_truth_used': False,
    'base_source': str(source), 'working_module_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest(),
    'results': results}
suffix = '_drawer8145'
output = root / f'coordination/bounded_skills_20261016/reports/handle_reference_pair_CPU_20261018{suffix}.json'
output.write_text(json.dumps(report, indent=2) + '\n')
