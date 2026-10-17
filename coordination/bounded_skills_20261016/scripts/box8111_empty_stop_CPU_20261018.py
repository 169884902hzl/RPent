"""Replay public recorded controls until empty-jaw evidence, then screen a smooth stop."""
from pathlib import Path
from types import SimpleNamespace
import copy
import hashlib
import importlib.util
import json
import os
import pickle
import sys
os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
prep=root/'results/bounded_skills/feasibility_20261017/preparation'
sys.path.insert(0,str(root/'source_bounded_a961dfd_20261018'))
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.bounded_motion import SmoothMotion, measured_robot, public_control
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_self_filter import gripper_visual_boxes, gripper_at_measured_fingers
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_grasp_truth import contact_sample
from robots.libero.v5_reset_seed import attach_reset_seed
module_path=prep/'bounded_skills_empty_stop_dev_CPU_20261018.py'
spec=importlib.util.spec_from_file_location('robots.libero.bounded_skills',module_path)
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
base=root/'results/bounded_skills/feasibility_20261017/job8111_20'
path=next(base.glob('*oracle*/choices.jsonl')); rows=[json.loads(line) for line in path.open()]; row=rows[8]
manifest=json.loads((prep/'original20_manifest_cee33e8_calibrated.json').read_text())
case=next(c for c in manifest['cases'] if path.parent.name==c['name']+'_oracle_k4')
def checked(reference):
    content=Path(reference['path']).read_bytes();assert hashlib.sha256(content).hexdigest()==reference['sha256'];return content
saved=pickle.loads(checked(row['private_pre_execution_snapshot']))
calibration=json.loads(checked(manifest['robot_calibration_file']))
class PublicPrimitives:
    def __init__(self,simulator,obs):
        self.simulator=simulator;self.obs=obs;self.truth=[]
        self.env=SimpleNamespace(raw_obs=lambda:{k:self.obs[k] for k in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_joint_pos')},terminated=False,truncated=False)
    def _step_env(self,action):
        self.obs,_,_,_=self.simulator.step(np.asarray(action,dtype=np.float32))
        self.truth.append(contact_sample(self.simulator.env,'alphabet_soup_1'))
env=ControlEnv(bddl_file_name=case['bddl']['path'],use_camera_obs=False,has_renderer=False,has_offscreen_renderer=False,camera_names=[],ignore_done=True,horizon=10015)
attach_reset_seed(env);env.seed(0);env.reset()
try:
    env.set_init_state(saved['sim_state']);restore_actuators(env,saved['actuator_state'])
    flat_error=float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
    p=PublicPrimitives(env,env.env._get_observations(force_update=True));robot=measured_robot(p)
    xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
    geometry={**panda_geometry(xml),'visual_boxes':gripper_visual_boxes(str(xml))}
    def cloud(name):
        ref=row['public_geometry_evidence']['bounded_screen_e98_0_'+name];checked(ref)
        with np.load(ref['path']) as z:return z[z.files[0]]
    ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',robot['joint_positions_rad'],robot['eef_xyz_m'],robot['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'],warm_start=True)
    screen=PublicRouteScreen(cloud('scene'),gripper_at_measured_fingers(geometry,robot['finger_positions_m']),ik,opening=robot['gripper_opening_m'],contact_points=cloud('target'),contact_allowed=False,payload_local=cloud('payload_local'),initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']})
    adapter=module.MeasuredSkillAdapter.__new__(module.MeasuredSkillAdapter);adapter.held='e99';adapter.ex=SimpleNamespace(grasp_measurement_calibration=calibration)
    original=row['execution_details'][0]['execution']['trace'];prefix=[];trigger=None;max_error=0.
    for i,control in enumerate(original):
        public_control(p,control['action']);prefix.append(copy.deepcopy(control))
        max_error=max(max_error,float(np.linalg.norm(np.asarray(measured_robot(p)['eef_xyz_m'])-control['after']['eef_xyz_m'])))
        if adapter._empty_held_gripper(measured_robot(p)):
            trigger=i;break
    assert trigger is not None
    braking=SmoothMotion(p,screen)._brake(prefix,1.)
    report={'scope':'CPU public empty-jaw stop on exact saved carry prefix with private diagnostic labels only; not task/confirmation score','training_allowed':False,'gpu_used':False,'renderer_used':False,'private_labels_used_for_control':False,'runtime_base':'a961dfd','development_module':{'path':str(module_path),'sha256':hashlib.sha256(module_path.read_bytes()).hexdigest()},'snapshot':row['private_pre_execution_snapshot'],'choices_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'calibration':manifest['robot_calibration_file'],'flat_state_restore_error':flat_error,'original_controls':len(original),'trigger_zero_based':trigger,'trigger_opening_m':original[trigger]['after']['gripper_opening_m'],'max_prefix_eef_replay_error_m':max_error,'executed_controls':len(p.truth),'braking':{k:v for k,v in braking.items() if k!='screen'},'braking_screen':{k:v for k,v in braking.get('screen',{}).items() if k!='ik_checks'},'private_first_without_dual_contact':next((i for i,t in enumerate(p.truth) if not t['dual_finger_contact']),None),'private_samples':p.truth,'trace':prefix}
finally:env.close()
output=root/'coordination/bounded_skills_20261016/reports/box8111_empty_stop_private_CPU_20261018.json';output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('private_samples','trace','braking_screen')},indent=2))
