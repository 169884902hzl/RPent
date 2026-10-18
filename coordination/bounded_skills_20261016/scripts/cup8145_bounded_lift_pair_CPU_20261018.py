"""Pair the rejected scan and an existing clear nudge at a held-cup state.

Public saved collision inputs and current proprioception drive control; private
state/contact samples only restore and diagnose. No new sensor image is made.
"""
# ruff: noqa: E402 -- immutable source and CPU before robot imports
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_8e49152_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_at_measured_fingers
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_truth import contact_sample
from robots.libero.v5_reset_seed import attach_reset_seed

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8145_60').glob('*oracle*'))
choices=directory/'choices.jsonl'
row = json.loads(choices.read_text().splitlines()[11])
ref = row['private_pre_execution_snapshot']
raw = Path(ref['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == ref['sha256']
saved = pickle.loads(raw)
plan = json.loads((base/'preparation/original20_manifest_8e49152_fused_contact.json').read_text())
case = next(c for c in plan['cases'] if c['name']+'_oracle_k4' == directory.name)
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
def cloud(kind):
    with np.load(row['public_geometry_evidence'][f'bounded_screen_e6_1_{kind}']['path']) as z:
        return z[z.files[0]]
points,target,payload = cloud('scene'),cloud('target'),cloud('payload_local')
assert len(target)==0
clear_nudges=[c for c in row['request']['candidates'] if c['skill']=='nudge'
    and c['consequences']['collision'] is False and c['consequences']['ik_reachable'] is True]
assert any(c['parameters']=={'anchor_id':'e6','axis':'z','distance_m':.02} for c in clear_nudges)
env=ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,
    has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
results=[]
try:
    for method in ('old_scan','bounded_lift'):
        env.set_init_state(saved['sim_state'])
        obs=restore_actuators(env,saved['actuator_state'])
        residual=float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        assert residual<1e-8
        facade=SimpleNamespace(terminated=False,truncated=False,observation=obs,used=0)
        facade.raw_obs=lambda:facade.observation
        facade.execution_budget=lambda:{'used_sim_steps':facade.used,'remaining_sim_steps':10000-facade.used}
        samples=[contact_sample(env.env,'white_yellow_mug_1')]
        def step(action):
            ob,_,done,_=env.step(np.asarray(action,dtype=np.float32))
            facade.observation,facade.terminated=ob,bool(done)
            facade.used+=1
            samples.append(contact_sample(env.env,'white_yellow_mug_1'))
        p=SimpleNamespace(env=facade,_step_env=step)
        robot=measured_robot(p)
        request_proprio_residual = {key: float(np.max(np.abs(np.asarray(robot[key])
            - row['request']['robot'][key]))) for key in ('eef_xyz_m','eef_quat_xyzw')}
        geometry=gripper_at_measured_fingers(panda_geometry(xml),robot['finger_positions_m'])
        ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
            robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'],warm_start=True)
        screen=PublicRouteScreen(points,geometry,ik,opening=robot['gripper_opening_m'],
            contact_points=target,contact_allowed=True,payload_local=payload,
            initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
        offsets=([0.,0.,.04],[.04,0.,0.],[-.04,0.,0.],[0.,.04,0.],[0.,-.04,0.]) if method=='old_scan' else ([0.,0.,.02],)
        executions=[]
        for offset in offsets:
            goal=np.asarray(robot['eef_xyz_m'])+offset
            execution=SmoothMotion(p,screen).run([{'xyz_m':goal.tolist(),
                'quat_xyzw':robot['eef_quat_xyzw']}],gripper=1.)
            executions.append(execution)
            if execution['executed']:
                break
        delta=np.asarray(samples[-1]['target_com_xyz'])-samples[0]['target_com_xyz']
        result={'method':method,'restore_residual':residual,'controls':facade.used,
            'public_request_proprio_residual':request_proprio_residual,
            'body_delta_m':delta.tolist(),'stops':[e['stop_reason'] for e in executions],
            'dual_finger_contact_samples':sum(s['dual_finger_contact'] for s in samples),
            'sample_count':len(samples),'executions':executions,'private_samples':samples}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('executions','private_samples')}),flush=True)
finally:
    env.close()
output=root/'coordination/bounded_skills_20261016/reports/cup8145_bounded_lift_pair_CPU_20261018.json'
output.write_text(json.dumps({'scope':'same saved-state CPU physics diagnosis; not full task or v3 confirmation',
    'gpu_used':False,'renderer_used':False,'private_labels_used_for_control':False,'training':False,
    'case':case,'snapshot':ref,'source_commit':plan['source_commit'],'row':11,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results},indent=2)+'\n')
