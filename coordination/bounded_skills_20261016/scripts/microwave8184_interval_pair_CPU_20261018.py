"""Recompute saved public contact fits without issuing controls or rendering."""
# ruff: noqa: E402 -- select immutable source and CPU before geometry imports
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_9cacb71_20261018'))
import numpy as np

from robots.libero.bounded_payload import contact_axis_registration as original
from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers,
    gripper_visual_boxes,
    remove_current_gripper,
    remove_visual_robot,
)
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen

base = root/'coordination/bounded_skills_20261016'
new_path = base/'prototype/bounded_payload_quantized.py'
spec = importlib.util.spec_from_file_location('quantized_contact_payload', new_path)
new = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new)
directory = next((root/'results/bounded_skills/feasibility_20261017/job8184_120').glob('*oracle*'))
choices = directory/'choices.jsonl'
rows = [json.loads(line) for line in choices.open()]
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}


def load(path):
    with np.load(path) as stored:
        return stored[stored.files[0]]


def outcome(fit, direction):
    low, high = sorted(np.asarray(fit['compatible_axis_interval_m'])*np.sign(direction))
    if low >= .005:
        return 'success'
    if high <= -.005:
        return 'failure'
    if low > -.005 and high < .005:
        return 'no_effect'
    return 'unmeasured'


results = []
for row in rows:
    executions = row.get('execution_details', [])
    if not executions or 'public_contact_motion' not in executions[-1]['execution']:
        continue
    detail = executions[-1]['execution']
    public = detail['public_contact_motion']
    before, after = public['before_capture_step'], public['after_capture_step']
    robot = detail['trace'][-1]['after']
    hand = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
    cloud = np.concatenate([load(directory/(c+'_world_high.npz')/f'{after:02d}.npz').reshape(-1, 3)
                            for c in ('agentview', 'wrist')])
    cloud, _ = remove_current_gripper(cloud, robot['eef_xyz_m'], robot['eef_quat_xyzw'],
                                     hand, robot['gripper_opening_m'])
    ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
                         robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
    cloud, _ = ik.remove_measured_arm(cloud)
    cloud, _ = remove_visual_robot(cloud, ik)
    reference = load(directory/'bounded_contact_e114_reference.npz'/f'{before:02d}.npz')
    chosen = next(c for c in row['request']['candidates'] if c['id'] in row['decision']['candidate_ids'])
    distance = chosen['parameters']['distance_m']
    axis = 'xyz'.index(public['command_axis'])
    old_fit, new_fit = (f(reference, cloud, axis, distance)
                        for f in (original, new.contact_axis_registration))
    recorded = public['surface_registration']
    np.testing.assert_allclose(old_fit['compatible_axis_interval_m'], recorded['compatible_axis_interval_m'], atol=1e-12)
    np.testing.assert_allclose(old_fit['mean_capped_squared_residual_m2'], recorded['mean_capped_squared_residual_m2'], atol=1e-12)
    results.append({'index': row['index'], 'distance_m': distance,
                    'original': old_fit, 'corrected': new_fit,
                    'original_outcome': outcome(old_fit, distance),
                    'corrected_outcome': outcome(new_fit, distance)})
    print(row['index'], results[-1]['original_outcome'], results[-1]['corrected_outcome'], flush=True)
report = {'scope': 'exact saved public RGB-D and measured robot states; zero controls, no private truth',
          'gpu_used': False, 'private_truth_used': False, 'training': False,
          'choices': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest()},
          'corrected_payload_sha256': hashlib.sha256(new_path.read_bytes()).hexdigest(),
          'results': results}
(base/'reports/microwave8184_interval_pair_CPU_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
