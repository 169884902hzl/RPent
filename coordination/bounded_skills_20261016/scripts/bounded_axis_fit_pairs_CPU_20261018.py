from pathlib import Path
import json,os,sys,importlib.util,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.spatial.transform import Rotation
root=Path('/public/home/sunyihan/rpent_libero_eval');sys.path.insert(0,str(root/'source_bounded_1fde995_20261017'))
from robots.libero.bounded_self_filter import gripper_at_measured_fingers,gripper_visual_boxes,remove_current_gripper,remove_visual_robot
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
import robots.libero.bounded_payload as module
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml';geometry=panda_geometry(xml);geometry['visual_boxes']=gripper_visual_boxes(str(xml))
def load(path):
 with np.load(path) as f:return f[f.files[0]]
result=[]
for job,indices in [('8036_160',(3,4,6,7)),('8072_80',(2,3,4,5,6,7,8,9,15,23,24))]:
 p=next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*'));raw=(p/'choices.jsonl').read_bytes();rows=[json.loads(l) for l in raw.decode().splitlines()]
 for i in indices:
  row=rows[i];e=row['execution_details'][0]['execution']['public_contact_motion'];a,b=e['before_capture_step'],e['after_capture_step'];parameters=next(c['parameters'] for c in row['request']['candidates'] if c['id'] in row['decision']['candidate_ids'] and c['skill']=='nudge');anchor=parameters['anchor_id'];axis='xyz'.index(parameters['axis'])
  source=load(p/f'bounded_screen_{anchor}_1_target.npz'/f'{a:02d}.npz');source_paths=[]
  for kind in ('fixture_control','fixture_handle'):
   files=[d/f'{a:02d}.npz' for d in p.glob(kind+'_'+anchor+'_*') if (d/f'{a:02d}.npz').exists()]
   if files:source=np.concatenate([load(f) for f in files]);source_paths=files;break
  if source_paths:
   sensor=next(t['before'] for d in row['execution_details'] for t in d['execution'].get('trace',[]));hand=gripper_at_measured_fingers(geometry,sensor['finger_positions_m']);source,_=remove_current_gripper(source,sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],hand,sensor['gripper_opening_m']);ik=PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml',sensor['joint_positions_rad'],sensor['eef_xyz_m'],sensor['eef_quat_xyzw'],geometry['site_offset_in_gripper_m']);source,_=ik.remove_measured_arm(source);source,_=remove_visual_robot(source,ik)
  target=np.concatenate([load(p/f'bounded_screen_{anchor}_1_{n}.npz'/f'{b:02d}.npz') for n in ('scene','target')]);fit=module.contact_axis_registration(source,target,axis,parameters['distance_m']);outcome='unmeasured'
  if fit['accepted']:
   lo,hi=sorted(np.asarray(fit['compatible_axis_interval_m'])*np.sign(parameters['distance_m']));outcome='success' if lo>=.005 else 'failure' if hi<=-.005 else 'no_effect' if lo>-.005 and hi<.005 else 'unmeasured'
  r={'job':job,'decision':i,'parameters':parameters,'original_outcome':row['receipts'][0]['outcome'],'proposed_outcome':outcome,'public_fit':fit,'source_handle_paths':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in source_paths],'input_choices_sha256':hashlib.sha256(raw).hexdigest()};result.append(r);print(json.dumps(r),flush=True)
report={'scope':'CPU production axis-fit function on saved public depth; fixture reference is measured handle with public self filtering; current scene is saved voxel screen union,not full live raw scene; private labels added separately,original labels unchanged','function_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),'training_allowed':False,'rows':result}
p=root/'coordination/bounded_skills_20261016/reports/bounded_axis_fit_pairs_CPU_20261018.json';p.write_text(json.dumps(report,indent=2)+'\n')
