"""Measure temporal support of unowned public depth without any controls."""
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
directory = next((root/'results/bounded_skills/feasibility_20261017/job8249_60').glob('*oracle*'))
rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()[:13]]
row = rows[12]
def load(name, step):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    with np.load(path) as z:
        return z[z.files[0]]
points = np.unique(np.array([d['obstacle_point'] for d in row['candidate_screen_diagnostics']
    if d.get('skill') == 'carry_to' and d.get('obstacle_point')]), axis=0)
current_robot = row['request']['robot']
reference_robot = load('bounded_payload_reference_robot.json', 11)
old = load('bounded_payload_reference_target.npz', 11)
rotation = Rotation.from_quat(current_robot['eef_quat_xyzw']).as_matrix()
old_rotation = Rotation.from_quat(reference_robot['eef_quat_xyzw']).as_matrix()
predicted = ((old-reference_robot['eef_xyz_m'])@old_rotation)@rotation.T+current_robot['eef_xyz_m']
distance, ids = cKDTree(predicted).query(points)
records = []
for index in range(10, 13):
    r = rows[index]
    for key in r['public_geometry_evidence']:
        if not key.endswith('_payload_local'):
            continue
        capture = r['public_geometry_evidence'][key]['capture_step']
        if any(record['capture_step'] == capture for record in records):
            continue
        local = load(key+'.npz', capture)
        at = r['request']['robot']
        world = local@Rotation.from_quat(at['eef_quat_xyzw']).as_matrix().T+at['eef_xyz_m']
        now = local@rotation.T+current_robot['eef_xyz_m']
        records.append({'row': index, 'capture_step': capture, 'artifact': key,
            'nearest_at_capture_m': cKDTree(world).query(points)[0].tolist(),
            'nearest_rigid_transport_m': cKDTree(now).query(points)[0].tolist()})
report = {'scope': 'public saved temporal geometry only; zero controls/no new perception',
    'private_truth_used': False, 'gpu_used': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'points': points.tolist(), 'pre_lift_target_points': len(old),
    'nearest_rigid_prediction_m': distance.tolist(),
    'nearest_predicted_points': predicted[ids].tolist(), 'nearest_old_points': old[ids].tolist(),
    'eef_displacement_m': (np.asarray(current_robot['eef_xyz_m'])-reference_robot['eef_xyz_m']).tolist(),
    'captures': records}
(base/'reports/cup8249_temporal_support_CPU_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
