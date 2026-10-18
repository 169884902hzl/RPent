"""Restore one failed prefix and pair old/new public-surface route screens."""
# ruff: noqa: E402 -- select CPU and immutable executor before simulator imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='',LIBERO_TYPE='standard',OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_c3a78f8_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion,measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import separate_target_points
from robots.libero.v5_reset_seed import attach_reset_seed

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8161_100').glob('*oracle*'))
row = json.loads((directory/'choices.jsonl').read_bytes().splitlines()[4])
reference = row['private_pre_execution_snapshot']
raw = Path(reference['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == reference['sha256']
saved = pickle.loads(raw)
plan = json.loads((base/'preparation/original20_manifest_contact_retry_20261018.json').read_text())
case = next(c for c in plan['cases'] if c['name']+'_oracle_k4'==directory.name)
def load(path):
    with np.load(path) as z:
        return z[z.files[0]]
scene = load(row['public_geometry_evidence']['bounded_screen_e54_1_scene']['path'])
target = load(row['public_geometry_evidence']['bounded_screen_e54_1_target']['path'])
curved_path = root/'coordination/bounded_skills_20261016/reports/drawer8161_curved_current_contact.npz'
curved = load(curved_path)
new_target,new_scene = separate_target_points(np.concatenate([target,curved]),scene)
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
env = ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,
    has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
results = []
try:
    for method,points,contact in (('old',scene,target),('curved',new_scene,new_target)):
        env.set_init_state(saved['sim_state'])
        observation = restore_actuators(env,saved['actuator_state'])
        residual = float(np.max(abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        assert residual < 1e-8
        facade = SimpleNamespace(terminated=False,truncated=False,observation=observation,used=0)
        facade.raw_obs = lambda:facade.observation
        facade.execution_budget = lambda:{'used_sim_steps':facade.used,'remaining_sim_steps':10000-facade.used}
        def joints():
            sim = env.env.sim
            return {name:float(sim.data.qpos[sim.model.jnt_qposadr[i]]) for i,name in enumerate(sim.model.joint_names)
                if name and any(token in name for token in ('drawer','cabinet'))}
        before = joints()
        def step(action):
            ob,_,done,_ = env.step(np.asarray(action,dtype=np.float32))
            facade.observation,facade.terminated = ob,bool(done)
            facade.used += 1
        primitives = SimpleNamespace(env=facade,_step_env=step)
        robot = measured_robot(primitives)
        for name in ('eef_xyz_m','eef_quat_xyzw'):
            np.testing.assert_allclose(robot[name],row['request']['robot'][name],atol=1e-10)
        geometry = gripper_at_measured_fingers(panda_geometry(xml),robot['finger_positions_m'])
        ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
            robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
        screen = PublicRouteScreen(points,geometry,ik,opening=robot['gripper_opening_m'],
            contact_points=contact,contact_allowed=True,
            initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
        goal = {'xyz_m':(np.asarray(robot['eef_xyz_m'])+[0.,.02,0.]).tolist(),
            'quat_xyzw':robot['eef_quat_xyzw']}
        execution = SmoothMotion(primitives,screen).run([goal],gripper=1.)
        after = joints()
        result = {'method':method,'restore_residual':residual,'controls':facade.used,
            'stop_reason':execution['stop_reason'],'native_success':facade.terminated,
            'private_joints_before':before,'private_joints_after':after,
            'private_joint_delta':{k:after[k]-v for k,v in before.items()},'execution':execution}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k!='execution'}),flush=True)
finally:
    env.close()
report = {'scope':'CPU one-prefix physics diagnosis;not a complete episode or confirmation',
    'gpu_used':False,'renderer_used':False,'training':False,'private_truth_used_for_control':False,
    'snapshot':reference,'case':case,'curved_geometry_sha256':hashlib.sha256(curved_path.read_bytes()).hexdigest(),
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results}
output = root/'coordination/bounded_skills_20261016/reports/drawer8161_curved_motion_pair_CPU_20261018.json'
output.write_text(json.dumps(report,indent=2)+'\n')
