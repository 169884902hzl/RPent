from pathlib import Path
from types import SimpleNamespace
import hashlib,importlib.util,json,os,sys
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval');sys.path.insert(0,str(root/'source_bounded_cee33e8_20261018'))
import numpy as np
from robots.libero.bounded_self_filter import gripper_at_measured_fingers,gripper_visual_boxes,remove_current_gripper,remove_visual_robot
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.bounded_payload import contact_axis_registration
module_path=root/'results/bounded_skills/feasibility_20261017/preparation/bounded_skills_handle_reference_dev_CPU_20261018.py'
spec=importlib.util.spec_from_file_location('robots.libero.bounded_skills',module_path);bs=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bs;spec.loader.exec_module(bs)
p=next((root/'results/bounded_skills/feasibility_20261017/job8103_80').glob('*oracle*/choices.jsonl'));raw=p.read_bytes();rows=[json.loads(l) for l in raw.decode().splitlines()]
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml';geometry={**panda_geometry(xml),'visual_boxes':gripper_visual_boxes(str(xml))}
contact_robot=rows[1]['execution_details'][0]['execution']['trace'][-1]['after']
def load(name,step):
 path=p.parent/name/(f'{step:02d}'+Path(name).suffix)
 if path.suffix=='.json':return json.loads(path.read_text())
 z=np.load(path);return z[z.files[0]]
def raw_scene(sensor,step):
 points=np.concatenate([load(camera+'_world_high.npz',step).reshape(-1,3) for camera in ('agentview','wrist')])
 hand=gripper_at_measured_fingers(geometry,sensor['finger_positions_m'])
 points,_=remove_current_gripper(points,sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],hand,sensor['gripper_opening_m'])
 ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',sensor['joint_positions_rad'],sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],geometry['site_offset_in_gripper_m'])
 points,_=ik.remove_measured_arm(points);points,_=remove_visual_robot(points,ik)
 return points,ik
out=[]
for index in (2,3):
 row=rows[index];step=next(iter(row['public_geometry_evidence'].values()))['capture_step']
 sensor=row['execution_details'][0]['execution']['trace'][0]['before'];after_sensor=row['execution_details'][0]['execution']['trace'][-1]['after']
 before_scene,ik=raw_scene(sensor,step);after_scene,_=raw_scene(after_sensor,step+1)
 plan=next(d['plan'] for d in row['candidate_screen_diagnostics'] if d.get('stage')=='fixture_contact_plan' and d.get('anchor_id')=='e101')
 obs={'robot0_eef_pos':sensor['eef_xyz_m'],'robot0_eef_quat':sensor['eef_quat_xyzw'],'robot0_gripper_qpos':sensor['finger_positions_m'],'robot0_joint_pos':sensor['joint_positions_rad']}
 adapter=bs.MeasuredSkillAdapter.__new__(bs.MeasuredSkillAdapter)
 adapter.p=SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:obs));adapter.active='e101';adapter.held=None;adapter.geometry=geometry;adapter._base_geometry=(before_scene,ik)
 adapter.scene=SimpleNamespace(entities={});adapter.plans={'e101':plan};adapter.committed_grasps={'e101':{'plan':plan,'contact_robot':contact_robot}};adapter.withdrawal_contact=None;adapter._instance_pixels=lambda key:np.empty((0,3));adapter.instance_boundary_evidence={}
 adapter.ex=SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step,load=lambda name:load(name,step))))
 old=adapter._handle_pixels(plan['handle_measurement'],contact_surface=True)
 current=adapter._contact_pixels('e101',handle_only=True)
 fit=contact_axis_registration(current,after_scene,1,-.01)
 record={'decision':index,'before_capture_step':step,'old_reference_points':len(old),'current_reference_points':len(current),'axis_surface_fit':fit,'recovery_evidence':adapter.instance_boundary_evidence.get('e101',[])}
 out.append(record);print(json.dumps({k:v for k,v in record.items() if k!='recovery_evidence'}),flush=True)
report={'scope':'CPU saved-public drawer contact reference/axis registration, no simulation controls or private labels; not a task result','training_allowed':False,'source_base':'cee33e8','working_module_sha256':hashlib.sha256(module_path.read_bytes()).hexdigest(),'choices_sha256':hashlib.sha256(raw).hexdigest(),'rows':out}
(root/'coordination/bounded_skills_20261016/reports/drawer8103_handle_reference_CPU_20261018.json').write_text(json.dumps(report,indent=2)+'\n')
