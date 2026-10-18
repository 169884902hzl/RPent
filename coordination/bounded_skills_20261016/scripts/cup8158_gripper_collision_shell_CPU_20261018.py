"""Test whether static collision pads explain public gripper pixels missed by visuals."""

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_276456d_20261018'))
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_self_filter import gripper_at_measured_fingers, gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry

directory = next((root/'results/bounded_skills/feasibility_20261017/job8158_60').glob('*oracle*'))
rows = [json.loads(line) for line in (directory/'choices.jsonl').open()]
robot = rows[15]['execution_details'][-1]['execution']['trace'][-1]['after']
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
geometry = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
site = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
point = np.array([.0107914749532938, .08394207060337067, .7108669877052307])
local = (point-robot['eef_xyz_m'])@site
results = []
for group in ('visual_boxes', 'boxes'):
    results.append({'group': group, 'hull_residuals_m': {box['name']:
        float(np.max(np.asarray(box['convex_halfspaces'])[:, :3]@local
            +np.asarray(box['convex_halfspaces'])[:, 3])) for box in geometry[group]}})
output = root/'coordination/bounded_skills_20261016/reports/cup8158_gripper_collision_shell_CPU_20261018.json'
report = {'scope': 'CPU static robot geometry and saved public proprioception only, zero controls',
    'training': False, 'private_truth_used': False, 'point': point.tolist(),
    'robot': robot, 'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest(), 'results': results}
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(results, indent=2))
