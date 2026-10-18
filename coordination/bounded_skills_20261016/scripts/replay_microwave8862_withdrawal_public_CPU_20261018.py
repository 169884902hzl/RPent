"""Compare saved public scan screens with and without the released identity."""
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_chunk_v3_self_filter_20261018_b6cf6d0'
sys.path.insert(0, str(source))
import numpy as np
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen

base = root / 'results/bounded_skills/feasibility_20261017/job8862_120'
directory = base / 'microwave_close_libero_90_t33_s0_oracle_k4'
choices = directory / 'choices.jsonl'
rows = [json.loads(line) for line in choices.read_text().splitlines()]
row = rows[7]
trace = rows[4]['execution_details'][-1]['execution']['trace']
sensor = trace[-1]['after']
assert all(action['steps_used'] == 0 for item in rows[5:8] for action in item.get('receipts', []))
assert np.array_equal(sensor['eef_xyz_m'], row['request']['robot']['eef_xyz_m'])
geometry = panda_geometry(root / '.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')
geometry = gripper_at_measured_fingers(geometry, sensor['finger_positions_m'])
xml = root / '.venv/lib/python3.10/site-packages/robosuite/models/assets/robots/panda/robot.xml'
diagnostic = next(item for item in row['candidate_screen_diagnostics'] if item.get('skill') == 'nudge')
start = diagnostic['at']
evidence = row['public_geometry_evidence']
inputs, results = {}, []
for name in ('bounded_screen_None_0', 'bounded_screen_e114_1'):
    clouds = {}
    for kind in ('scene', 'target', 'payload_local'):
        artifact = evidence[name+'_'+kind]
        raw = Path(artifact['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact['sha256']
        with np.load(artifact['path']) as data:
            clouds[kind] = data[data.files[0]]
        inputs[name+'_'+kind] = artifact
    for offset in ([0., 0., .04], [.04, 0., 0.], [-.04, 0., 0.], [0., .04, 0.], [0., -.04, 0.]):
        ik = PublicPoseScreen(xml, sensor['joint_positions_rad'], sensor['eef_xyz_m'],
            sensor['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'], warm_start=True)
        screen = PublicRouteScreen(clouds['scene'], geometry, ik, opening=sensor['gripper_opening_m'],
            contact_points=clouds['target'], contact_allowed=name.endswith('e114_1'),
            payload_local=clouds['payload_local'], initial_pose={
                'xyz_m': sensor['eef_xyz_m'], 'quat_xyzw': sensor['eef_quat_xyzw']})
        end = dict(start, xyz_m=(np.asarray(start['xyz_m'])+offset).tolist())
        result = screen([start, end])
        results.append(dict(screen=name, offset_m=offset,
            **{key: result.get(key) for key in ('passed', 'reason', 'collision', 'ik_reachable',
                'path_min_clearance_m', 'at', 'counts', 'target_counts', 'samples')}))
report = dict(source_snapshot=str(source), public_inputs=inputs, results=results,
    public_sensor_source=dict(path=str(choices), row_index=4, action='wrist_scan', sample='last_after'),
    public_sensor=sensor, controls=0, fresh_observations=0, private_truth_used=False,
    scope='captured scan-start pose and 4cm straight sweeps; not a complete SmoothMotion braking replay or task result',
    training=False, confirmation=False,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
output = root / 'coordination/bounded_skills_20261016/reports/microwave8862_withdrawal_public_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(output), results=results)))
