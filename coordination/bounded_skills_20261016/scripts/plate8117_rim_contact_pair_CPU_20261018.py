"""Pair measured rim contacts from one saved state; no policy or score change."""
# ruff: noqa: E402 -- immutable source and CPU before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0, str(root/'source_bounded_8e49152_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_reset_seed import attach_reset_seed

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8117_160').glob('*oracle*'))
choices = directory/'choices.jsonl'
rows = [json.loads(line) for line in choices.open()]
row = rows[1]
ref = row['private_pre_execution_snapshot']
raw = Path(ref['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == ref['sha256']
saved = pickle.loads(raw)
plan = json.loads((base/'preparation/original20_manifest_8e49152_fused_contact.json').read_text())
case = next(c for c in plan['cases'] if c['name']+'_oracle_k4' == directory.name)
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry = panda_geometry(xml)
robot_xml = xml.parent.parent/'robots/panda/robot.xml'
def cloud(kind):
    path = rows[0]['public_geometry_evidence'][f'bounded_screen_e99_1_{kind}']['path']
    with np.load(path) as z:
        return z[z.files[0]]
points, target = cloud('scene'), cloud('target')
contact = next(d for d in rows[0]['candidate_screen_diagnostics']
    if d.get('stage') == 'measured_surface_contact' and d['anchor_id'] == 'e99')
patch = np.array(contact['contact_xyz_m'])
local = target[np.linalg.norm(target[:, :2]-patch[:2], axis=1) <= .01]
assert len(local) >= 8
# Actual observed low rim point, not a private object coordinate or invented depth.
low = local[np.argmin(local[:, 2])]
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
results = []
try:
    for method in ('recorded_top_rim', 'measured_low_rim'):
        env.set_init_state(saved['sim_state'])
        obs = restore_actuators(env, saved['actuator_state'])
        residual = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        assert residual < 1e-8
        facade = SimpleNamespace(terminated=False, truncated=False, observation=obs, used=0)
        facade.raw_obs = lambda: facade.observation
        facade.execution_budget = lambda: {'used_sim_steps': facade.used,
            'remaining_sim_steps': 10000-facade.used}
        body_id = env.env.obj_body_id['plate_1']
        samples = []
        def sample():
            sim = env.env.sim
            touching = []
            for c in sim.data.contact[:sim.data.ncon]:
                if int(sim.model.geom_bodyid[c.geom1]) == body_id or int(sim.model.geom_bodyid[c.geom2]) == body_id:
                    names = [sim.model.geom_id2name(int(g)) for g in (c.geom1, c.geom2)]
                    if any(n and ('finger' in n or 'hand' in n) for n in names):
                        touching.append(names)
            samples.append({'step': facade.used, 'body_xyz_m': sim.data.body_xpos[body_id].tolist(),
                'finger_contacts': touching})
        def step(action):
            ob, _, done, _ = env.step(np.asarray(action, dtype=np.float32))
            facade.observation, facade.terminated = ob, bool(done)
            facade.used += 1
            sample()
        p = SimpleNamespace(env=facade, _step_env=step)
        robot = measured_robot(p)
        ik = PublicPoseScreen(robot_xml, robot['joint_positions_rad'], robot['eef_xyz_m'],
            robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'], warm_start=True)
        screen = PublicRouteScreen(points, geometry, ik, opening=robot['gripper_opening_m'],
            contact_points=target, contact_allowed=True,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']})
        sample()
        executions = []
        if method == 'measured_low_rim':
            goal = np.asarray(robot['eef_xyz_m']) + low-patch
            executions.append(SmoothMotion(p, screen).run([{'xyz_m': goal.tolist(),
                'quat_xyzw': robot['eef_quat_xyzw']}], gripper=-1.))
        permitted = not executions or executions[-1]['executed'] and executions[-1]['stop_reason'] == 'endpoint'
        if permitted:
            for _ in range(15):
                step([0., 0., 0., 0., 0., 0., 1.])
            for _ in range(3):
                robot = measured_robot(p)
                goal = np.asarray(robot['eef_xyz_m'])+[0., .02, 0.]
                execution = SmoothMotion(p, screen).run([{'xyz_m': goal.tolist(),
                    'quat_xyzw': robot['eef_quat_xyzw']}], gripper=1.)
                executions.append(execution)
                if not execution['executed'] or execution['stop_reason'] != 'endpoint':
                    break
        delta = np.asarray(samples[-1]['body_xyz_m'])-samples[0]['body_xyz_m']
        result = {'method': method, 'restore_residual': residual, 'controls': facade.used,
            'body_delta_m': delta.tolist(), 'body_xy_displacement_m': float(np.linalg.norm(delta[:2])),
            'finger_contact_samples': sum(bool(s['finger_contacts']) for s in samples),
            'stops': [e['stop_reason'] for e in executions], 'executions': executions, 'private_samples': samples}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('executions', 'private_samples')}), flush=True)
finally:
    env.close()
output = root/'coordination/bounded_skills_20261016/reports/plate8117_rim_contact_pair_CPU_20261018.json'
output.write_text(json.dumps({'scope': 'saved-state CPU contact diagnosis only; not task score',
    'gpu_used': False, 'training': False, 'private_labels_used_for_control': False,
    'snapshot': ref, 'public_recorded_patch_m': patch.tolist(), 'public_low_patch_m': low.tolist(),
    'local_public_points': len(local), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'results': results}, indent=2)+'\n')
