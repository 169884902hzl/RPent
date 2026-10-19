"""Test a measured panel-normal alignment at the first blocked push, on CPU."""
# ruff: noqa: E402 -- pin captured classes and hide GPUs before imports
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_directional_contact_20261018_4db4ea4'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_geometric_grasp import side_site_rotation

directory, = (root/'results/bounded_skills/feasibility_20261017/job9539_120').glob('*oracle_k4')
raw = (directory/'choices.jsonl').read_bytes()
rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
records = []
for index in (1, 3, 4):
    row = rows[index]
    reference = row['private_prefix_annotation_state']
    adapter = load_annotation_state(reference['path'], reference['sha256'])['adapter']
    started = time.monotonic()
    prediction = PublicPrefixPrediction(adapter, row['request'])
    plan = prediction.adapter.plans['e114']
    robot = prediction.sensor
    normal = np.asarray(plan['surface_measurement']['normal_xyz'])
    current = Rotation.from_quat(robot['eef_quat_xyzw'])
    site = current.as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    tangent = site[:, 0]-normal*(site[:, 0]@normal)
    tangent /= np.linalg.norm(tangent)
    desired = Rotation.from_matrix(side_site_rotation(tangent, -normal)
        @Rotation.from_euler('z', np.pi/2).as_matrix())
    align = {'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': desired.as_quat().tolist()}
    motion = SmoothMotion(prediction.adapter.p,
        prediction._screen('e114', contact=True), prediction.adapter.config)
    _, _, _, evidence = motion.prepare([align])
    records.append({'index': index, 'context': reference,
        'normal_xyz': normal.tolist(), 'align_pose': align,
        'angle_rad': float((desired*current.inv()).magnitude()),
        'screen': evidence, 'cpu_s': time.monotonic()-started})
report = {'source': str(source), 'records': records,
    'choices_sha256': hashlib.sha256(raw).hexdigest(),
    'scope': 'CPU hypothesis only; existing full swept-mesh and IK checks, finger-only contact',
    'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False, 'private_goals_used': False,
    'training': False, 'confirmation': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output = root/'coordination/bounded_skills_20261016/reports/microwave9539_contact_alignment_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(output), 'records': [{key: row[key]
    for key in ('index', 'angle_rad', 'cpu_s')} | {'passed': row['screen']['passed'],
    'reason': row['screen']['reason']} for row in records]}))
