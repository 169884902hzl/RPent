"""Try measured rim approaches on four public axes; private labels diagnose only."""
# ruff: noqa: E402 -- immutable source and CPU before simulator imports
import hashlib
import json
import math
import os
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='',LIBERO_TYPE='standard',OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_bc160ff_20261018'))
import numpy as np
from scipy.spatial.transform import Rotation
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion,measured_robot
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_geometric_grasp import collision_counts,panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_reset_seed import attach_reset_seed

base=root/'results/bounded_skills/feasibility_20261017'
directory=next((base/'job8117_160').glob('*oracle*'))
p=directory/'choices.jsonl';captured=p.read_bytes();row=json.loads(captured.splitlines()[0])
ref=row['private_pre_execution_snapshot'];raw=Path(ref['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest()==ref['sha256'];saved=pickle.loads(raw)
plan=json.loads((base/'preparation/original20_manifest_bc160ff_held_nudge.json').read_text())
case=next(c for c in plan['cases'] if c['name']+'_oracle_k4'==directory.name)
def cloud(kind):
    with np.load(row['public_geometry_evidence'][f'bounded_screen_e99_1_{kind}']['path']) as z:
        return z[z.files[0]]
points,target=cloud('scene'),cloud('target')
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry=panda_geometry(xml)
contact=next(d for d in row['candidate_screen_diagnostics'] if d.get('stage')=='measured_surface_contact' and d['anchor_id']=='e99')
original=next(c for c in contact['candidates'] if (c.get('screen') or {}).get('passed'))
quat=original['quat_xyzw'];site=Rotation.from_quat(quat).as_matrix()@Rotation.from_euler('z',-math.pi/2).as_matrix()
pads=[b for b in geometry['boxes'] if b['name'].endswith('_pad')]
tip=np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in pads],axis=0)
tip[2]=max(b['upper'][2] for b in geometry['boxes'] if 'finger' in b['name'])
env=ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,
    has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
attach_reset_seed(env);env.seed(0);env.reset();results=[]
try:
    for axis,sign in ((0,-1),(0,1),(1,-1),(1,1)):
        env.set_init_state(saved['sim_state']);obs=restore_actuators(env,saved['actuator_state'])
        residual=float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
        assert residual<1e-8
        direction=np.zeros(3);direction[axis]=sign
        projection=target@direction;edge=target[projection>=np.quantile(projection,.97)]
        low=edge[edge[:,2]<=np.quantile(edge[:,2],.1)];patch=low[np.argmin(np.linalg.norm(low-np.median(low,axis=0),axis=1))]
        facade=SimpleNamespace(terminated=False,truncated=False,observation=obs,used=0)
        facade.raw_obs=lambda:facade.observation
        facade.execution_budget=lambda:{'used_sim_steps':facade.used,'remaining_sim_steps':10000-facade.used}
        body_id=env.env.obj_body_id['plate_1'];samples=[]
        def sample():
            sim=env.env.sim;contacts=[]
            for c in sim.data.contact[:sim.data.ncon]:
                if int(sim.model.geom_bodyid[c.geom1])==body_id or int(sim.model.geom_bodyid[c.geom2])==body_id:
                    names=[sim.model.geom_id2name(int(g)) for g in (c.geom1,c.geom2)]
                    if any(n and ('finger' in n or 'hand' in n) for n in names):contacts.append(names)
            samples.append({'step':facade.used,'body_xyz_m':sim.data.body_xpos[body_id].tolist(),'finger_contacts':contacts})
        def step(action):
            ob,_,done,_=env.step(np.asarray(action,dtype=np.float32));facade.observation=ob
            facade.terminated=bool(done);facade.used+=1;sample()
        p=SimpleNamespace(env=facade,_step_env=step);robot=measured_robot(p)
        ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],
            robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'],warm_start=True)
        screen=PublicRouteScreen(points,geometry,ik,opening=robot['gripper_opening_m'],
            contact_points=target,contact_allowed=True,
            initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
        xyz=patch-site@tip;entry=xyz+[0.,0.,.12];height=max(robot['eef_xyz_m'][2],entry[2])+.08
        route=[{'xyz_m':[*robot['eef_xyz_m'][:2],height],'quat_xyzw':robot['eef_quat_xyzw']},
            {'xyz_m':[*entry[:2],height],'quat_xyzw':quat},
            {'xyz_m':entry.tolist(),'quat_xyzw':quat},{'xyz_m':xyz.tolist(),'quat_xyzw':quat}]
        sample()
        closure=None
        for opening in np.linspace(.08,0.,9):
            external=collision_counts(points,xyz,site,geometry,opening,clearance_m=.004)
            own=collision_counts(target,xyz,site,geometry,opening,clearance_m=.004)
            if any(external.values()) or own.get('palm',0):
                closure={'opening_m':float(opening),'scene':external,'target':own};break
        execution=({'executed':False,'stop_reason':'closure_sweep_collision','closure':closure}
            if closure else SmoothMotion(p,screen).run(route,gripper=-1.))
        executions=[execution]
        if execution['executed'] and execution['stop_reason']=='endpoint':
            for _ in range(15):step([0.,0.,0.,0.,0.,0.,1.])
            for _ in range(4):
                if facade.terminated:break
                robot=measured_robot(p);goal=np.asarray(robot['eef_xyz_m'])-.02*direction
                execution=SmoothMotion(p,screen).run([{'xyz_m':goal.tolist(),'quat_xyzw':robot['eef_quat_xyzw']}],gripper=1.)
                executions.append(execution)
                if not execution['executed'] or execution['stop_reason']!='endpoint':break
        delta=np.asarray(samples[-1]['body_xyz_m'])-samples[0]['body_xyz_m']
        result={'outward_axis':'xyz'[axis],'outward_sign':sign,'public_patch_m':patch.tolist(),
            'restore_residual':residual,'controls':facade.used,'body_delta_m':delta.tolist(),
            'inward_displacement_m':float(-delta@direction),'native_success':facade.terminated,
            'stops':[e['stop_reason'] for e in executions],
            'finger_contact_samples':sum(bool(s['finger_contacts']) for s in samples),
            'executions':executions,'private_samples':samples}
        results.append(result);print(json.dumps({k:v for k,v in result.items() if k not in ('executions','private_samples')}),flush=True)
finally:env.close()
out=root/'coordination/bounded_skills_20261016/reports/plate8117_axis_rim_pair_CPU_20261018.json'
out.write_text(json.dumps({'scope':'four measured-axis contact candidates at one original saved state;CPU development only',
    'gpu_used':False,'renderer_used':False,'training':False,'private_labels_used_for_control':False,
    'snapshot':ref,'public_choices_prefix_sha256':hashlib.sha256(captured).hexdigest(),
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results},indent=2)+'\n')
