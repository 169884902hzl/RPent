from pathlib import Path
from types import SimpleNamespace
import hashlib,importlib.util,json,os,sys
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_11a73af_20261017'))
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry,collision_counts
prep=root/'results/bounded_skills/feasibility_20261017/preparation'
modules={}
for name,filename in [('robots.libero.v5_grasp_geometry','grasp_geometry_sparse_dev_CPU_20261018.py'),('robots.libero.bounded_skills','bounded_skills_sparse_dev_CPU_20261018.py')]:
 path=prep/filename
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 modules[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
bs=module
real_sparse=bs.complete_sparse_instance_boundary
p=next((root/'results/bounded_skills/feasibility_20261017/job8071_20').glob('*oracle*/choices.jsonl'))
raw=p.read_bytes();rows=[json.loads(l) for l in raw.decode().splitlines()];row=rows[4]
sensor=rows[3]['execution_details'][-1]['execution']['trace'][-1]['after']
def load(path):
 path=Path(path)
 if path.suffix=='.json':return json.loads(path.read_text())
 z=np.load(path);return z[z.files[0]]
anchor=next(a for a in row['request']['anchors'] if a['id']=='e99')
centre,size=np.asarray(anchor['xyz_m']),np.asarray(anchor['size_m'])
entity=SimpleNamespace(id='e99',name=anchor['label'],part_of=None,lower=centre-size/2,upper=centre+size/2)
views={}
for camera in ('agentview','wrist'):
 world=load(p.parent/(camera+'_world_high.npz')/'05.npz')
 mask=load(row['perception_evidence']['e99']['sam_mask_files'][camera]['path']).astype(bool)
 views[camera]={'source_step':5,'xyz_world':world[mask]}
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
obs={'robot0_eef_pos':sensor['eef_xyz_m'],'robot0_eef_quat':sensor['eef_quat_xyzw'],'robot0_gripper_qpos':sensor['finger_positions_m'],'robot0_joint_pos':sensor['joint_positions_rad']}
primitive=SimpleNamespace(env=SimpleNamespace(raw_obs=lambda:obs))
recent=rows[3]['execution_details'][-1]['execution']['trace'][-3:]
primitive._bounded_motion_samples=list(enumerate([recent[0]['before'],*[t['after'] for t in recent]]));primitive._bounded_control_index=3
wanted={'s0_a0_side_1_orient_at_pregrasp','s7_a0_oblique_-1'}
diag=next(d for d in row['candidate_screen_diagnostics'] if d.get('stage')=='grasp_route_search' and d.get('anchor_id')=='e99')
results=[]
for version in ('old','sparse'):
 bs.complete_sparse_instance_boundary=(real_sparse if version=='sparse' else lambda world,mask:(mask.copy(),{'disabled_for_pair':True}))
 adapter=bs.MeasuredSkillAdapter.__new__(bs.MeasuredSkillAdapter)
 adapter.p=primitive;adapter.geometry={**panda_geometry(xml),'visual_boxes':gripper_visual_boxes(str(xml))};adapter.robot_xml=xml.parent.parent/'robots/panda/robot.xml'
 adapter._instance_cache={};adapter._screen_cache={};adapter._base_geometry=None;adapter.held=None;adapter.active=None;adapter.payload_reference=None;adapter.instance_boundary_evidence={};adapter.record_public_geometry=False
 adapter.scene=SimpleNamespace(entities={'e99':entity},measurement_clouds_by_view={'e99':views},measurement_clouds={})
 adapter.ex=SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=5,load=lambda name:load(p.parent/name/('05'+Path(name).suffix)))))
 # The saved ordinary, unheld object has no fixture/contact continuation.
 adapter._contact_pixels=adapter._instance_pixels
 screen=adapter._cloud_and_ik('e99',contact=True)
 for c in diag['candidates']:
  if c['id'] not in wanted:continue
  route=[{'xyz_m':w['xyz'],'quat_xyzw':w['body_quat_xyzw']} for w in c['route']]
  trajectory,_,_,evidence=SmoothMotion(primitive,screen).prepare(route)
  closure=[]
  if evidence['passed']:
   site=Rotation.from_quat(c['body_quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix()
   for opening in np.linspace(.08,0,9):
    ext=collision_counts(screen.points,c['xyz'],site,adapter.geometry,opening,clearance_m=.004)
    own=collision_counts(screen.target,c['xyz'],site,adapter.geometry,opening,clearance_m=.004)
    if any(ext.values()) or own.get('palm',0):closure.append({'opening':float(opening),'scene':ext,'target':own});break
  result={'version':version,'candidate':c['id'],'route_passed':bool(evidence['passed']),'reason':evidence['reason'],'closure':closure,'passed':bool(evidence['passed'] and not closure),'scene_points':len(screen.points),'target_points':len(screen.target),'boundary_evidence':adapter.instance_boundary_evidence['e99']}
  results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='boundary_evidence'}),flush=True)
report={'scope':'paired production instance reconstruction and route/closure CPU check using saved public RGB-D, original SAM and proprioception; no controls, private labels, training or confirmation','source_base':'11a73af','development_modules':modules,'choices_sha256':hashlib.sha256(raw).hexdigest(),'row':4,'results':results}
(root/'coordination/bounded_skills_20261016/reports/box8071_sparse_production_route_CPU_20261018.json').write_text(json.dumps(report,indent=2)+'\n')
