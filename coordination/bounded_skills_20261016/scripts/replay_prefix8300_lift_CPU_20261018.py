"""Re-screen saved public prefix geometry without controls or fresh SAM calls."""
# ruff: noqa: E402 -- select an immutable source before optional robot imports
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--raw-rgbd', action='store_true')
parser.add_argument('--working-modules', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))
if args.working_modules:
    for name in ('bounded_screen', 'bounded_chunk', 'bounded_skills'):
        spec = importlib.util.spec_from_file_location('robots.libero.'+name, args.working_modules/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

import numpy as np

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_state import Entity

root = Path('/public/home/sunyihan/rpent_libero_eval')
path = next((root/'results/bounded_skills/feasibility_20261017/job8300_0').glob('*oracle_k4/choices.jsonl'))
line = path.read_bytes().splitlines()[0]
row = json.loads(line)
request = row['request']
initial = next(d['execution']['trace'][0]['before'] for d in row['execution_details']
               if d.get('execution', {}).get('trace'))
obs = dict(robot0_eef_pos=initial['eef_xyz_m'], robot0_eef_quat=initial['eef_quat_xyzw'],
           robot0_joint_pos=initial['joint_positions_rad'], robot0_gripper_qpos=initial['finger_positions_m'])
env = SimpleNamespace(raw_obs=lambda: obs, execution_budget=lambda: {
    'used_sim_steps': 0, 'remaining_sim_steps': 10000})
entities = {}
for a in request['anchors']:
    centre, size = np.array(a['xyz_m']), np.array(a['size_m'])
    entities[a['id']] = Entity(a['id'], a['label'], tuple(centre), tuple(centre-size/2),
        tuple(centre+size/2), True, 0)
scene = SimpleNamespace(entities=entities, measurement_clouds={}, view_axes=([1., 0., 0.], [0., 1., 0.]),
                        dual_view_fusion_v1=True)
executor = SimpleNamespace(p=SimpleNamespace(env=env), scene=scene)
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
adapter = MeasuredSkillAdapter(executor, xml, allow_vla=False)
adapter.target_cache = dict(entities)
if args.raw_rgbd:
    from PIL import Image

    def load(name):
        file = path.parent/name/(f'00{Path(name).suffix}')
        if file.suffix == '.json':
            return json.loads(file.read_bytes())
        with np.load(file) as stream:
            return stream[stream.files[0]]
    scene.measurement_clouds_by_view = {}
    for key, measurement in row['perception_evidence'].items():
        views = {}
        for camera, artifact in measurement.get('sam_mask_files', {}).items():
            mask_path = Path(artifact['path'])
            raw = mask_path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == artifact['sha256']
            if mask_path.suffix == '.npz':
                with np.load(mask_path) as stream:
                    mask = stream[stream.files[0]].astype(bool)
            else:
                mask = np.asarray(Image.open(mask_path)).astype(bool)
            views[camera] = dict(source_step=0, xyz_world=load(camera+'_world_high.npz')[mask])
        scene.measurement_clouds_by_view[key] = views
    executor.toolkit = SimpleNamespace(_state=SimpleNamespace(latest_step=0, load=load))
for d in row['candidate_screen_diagnostics']:
    if d.get('stage') != 'grasp_route_search' or not d['selected']:
        continue
    selected = next(c for c in d['candidates'] if c['id'] == d['selected'])
    adapter.plans[d['anchor_id']] = dict(xyz_m=selected['xyz'], quat_xyzw=selected['body_quat_xyzw'],
        approach_xyz_m=selected['approach_xyz'], width_m=selected['width_m'], preferred_approach='above',
        preferred_path='over', approach_route=[dict(xyz_m=w['xyz'], quat_xyzw=w['body_quat_xyzw'])
            for w in selected['route'][:-1]])
artifacts = row['public_geometry_evidence']
inputs = []
clouds = {}
for name, artifact in artifacts.items():
    data = Path(artifact['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == artifact['sha256']
    with np.load(artifact['path']) as stream:
        clouds[name] = stream[stream.files[0]]
    inputs.append(artifact)

ik = PublicPoseScreen(adapter.robot_xml, initial['joint_positions_rad'], initial['eef_xyz_m'],
    initial['eef_quat_xyzw'], adapter.geometry['site_offset_in_gripper_m'], warm_start=True)

def saved_screen(key=None, *, contact=False):
    name = f'bounded_screen_{key}_{int(contact)}'
    return PublicRouteScreen(clouds[name+'_scene'],
        gripper_at_measured_fingers(adapter.geometry, initial['finger_positions_m']), ik,
        opening=initial['gripper_opening_m'], contact_points=clouds[name+'_target'],
        contact_allowed=contact, payload_local=clouds[name+'_payload_local'],
        initial_pose=dict(xyz_m=initial['eef_xyz_m'], quat_xyzw=initial['eef_quat_xyzw']))

if not args.raw_rgbd:
    adapter._cloud_and_ik = saved_screen
prediction = PublicPrefixPrediction(adapter, request)
lift = next(c for c in request['candidates'] if c['skill'] == 'lift'
            and c['parameters']['anchor_id'] == 'e99')
stages = []
for index in range(4):
    candidate = prediction.candidate(lift)
    screen = prediction._screen('e99', contact=prediction.adapter.active is not None)
    route = prediction.adapter._route('lift', lift['parameters'])
    _, _, _, evidence = SmoothMotion(prediction.adapter.p, screen, adapter.config).prepare(route)
    stages.append(dict(prefix=list(prediction.prefix), candidate=candidate, screen=evidence,
        payload_points=len(screen.payload), target_points=len(screen.target), scene_points=len(screen.points),
        predicted_robot=prediction.sensor.copy(), pending=prediction.pending, payload_id=prediction.payload_id))
    if index == 3:
        break
    chosen = next(c for c in request['candidates'] if c['id'] == row['decision']['candidate_ids'][index])
    prediction.advance(chosen)
if args.raw_rgbd and stages[-1]['screen'].get('obstacle_point') is not None:
    from scipy.spatial import cKDTree

    point = stages[-1]['screen']['obstacle_point']
    raw = adapter._base_geometry[0]
    target = adapter._contact_pixels('e99')
    cell = np.floor(np.asarray(point)/.004)
    members = raw[(np.floor(raw/.004) == cell).all(axis=1)]
    distances = cKDTree(target).query(members)[0]
    stages[-1]['blocker_voxel_provenance'] = dict(point=point, raw_pixels=len(members),
        exact_target_members=int((distances <= 1e-6).sum()),
        nearest_saved_screen_target_m=float(cKDTree(clouds['bounded_screen_e99_1_target']).query(point)[0]),
        member_distances_m=distances.tolist())
report = dict(scope='CPU reconstruction from saved public screen clouds; no new observations or controls',
    source=str(args.source), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    choices=str(path), first_row_sha256=hashlib.sha256(line).hexdigest(), inputs=inputs,
    private_truth_used=False, controls=0, fresh_sam_queries=0, training=False,
    raw_rgbd_reconstruction=args.raw_rgbd,
    working_modules=({name: hashlib.sha256((args.working_modules/(name+'.py')).read_bytes()).hexdigest()
                      for name in ('bounded_screen', 'bounded_chunk', 'bounded_skills')}
                     if args.working_modules else None), stages=stages)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(args.output), stages=[dict(prefix_length=len(s['prefix']),
    passed=s['screen']['passed'], reason=s['screen']['reason'], payload_points=s['payload_points'],
    at=s['screen'].get('at'), obstacle=s['screen'].get('obstacle_point')) for s in stages])))
