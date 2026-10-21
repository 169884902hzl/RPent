"""Replay frozen public geometry and compare it with actual public joint traces."""
import argparse,json,pickle,sys,hashlib,time
from pathlib import Path
from types import SimpleNamespace
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--case',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.source))
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from rpent.session import EnvState
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_motion import SmoothMotion
from robots.libero.bounded_robot_depth import current_robot_triangles
from scripts.probe_bounded_hybrid_d2 import load_public_gripper_calibration
from coordination.bounded_skills_20261016.scripts.fixed10_blocker_surface_distance_CPU_20261021 import closest_surface
class NoRPC:
 def call(self,*args,**kwargs):raise RuntimeError('unrecorded segmentation required')
saved=pickle.loads((a.case/'private_complete_common.pkl').read_bytes());runtime=saved['public_runtime']
store=object.__new__(EnvState);vars(store).update(runtime['artifact_state'])
scene=object.__new__(MeasuredScene);vars(scene).update(runtime['scene']);scene.toolkit=SimpleNamespace(_state=store);scene.rpc=NoRPC()
raw=saved['physics']['actuator_state']['observation_state']['cache'];observed={k:raw[k] for k in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_joint_pos')}
used=int(np.asarray(saved['physics']['counters']['_elapsed_steps']).item());env=SimpleNamespace(raw_obs=lambda:observed,execution_budget=lambda:{'used_sim_steps':used,'remaining_sim_steps':10000-used},terminated=False,truncated=False)
adapter=object.__new__(MeasuredSkillAdapter);vars(adapter).update(runtime['adapter']);adapter.scene=scene;adapter.p=SimpleNamespace(env=env);vars(adapter.p).update(runtime['primitive']);adapter.record_public_geometry=False
summary=json.loads((a.case/'summary.json').read_bytes());case=summary['registered_action']['case']
adapter.ex=SimpleNamespace(toolkit=scene.toolkit,instruction=scene.instruction,grasp_measurement_calibration=load_public_gripper_calibration(case['grasp_measurement_calibration']))
# Keep the exact frozen public caches used by both physical arms.
# Rebuilding would require unrecorded SAM point prompts.
skill=summary['registered_action']['candidate']['skill'];params=summary['registered_action']['candidate']['parameters']
contact=(adapter.active or (adapter.withdrawal_contact or {}).get('anchor_id')) if skill=='observe' else None
screen=adapter._cloud_and_ik(params.get('anchor_id') if skill=='move_to' else contact,contact=contact is not None)
signature=hashlib.sha256()
for cloud in (screen.points,screen.target,screen.payload):
 array=np.asarray(cloud,dtype='<f8');signature.update(str(array.shape).encode());signature.update(array.tobytes())
if signature.hexdigest()!=summary['arms'][0]['public_screen_input_sha256']:
 raise ValueError('CPU replay public screen inputs differ from physical branch')
held=adapter._instance_pixels(adapter.held) if adapter.held else np.empty((0,3))
_,_,poses,verdict=SmoothMotion(adapter.p,screen,adapter.config).prepare(summary['route'])
points=[]
for key in ('public_scene_collision_points','public_target_collision_points'):
 points.extend(xyz for group in verdict.get(key,{}).values() for xyz in group)
if verdict.get('arm_screen',{}).get('obstacle_point'):points.append(verdict['arm_screen']['obstacle_point'])
points=np.array(points).reshape(-1,3)
robot={'eef_xyz_m':np.asarray(observed['robot0_eef_pos']).tolist(),'eef_quat_xyzw':np.asarray(observed['robot0_eef_quat']).tolist(),'finger_positions_m':np.asarray(observed['robot0_gripper_qpos']).tolist(),'joint_positions_rad':np.asarray(observed['robot0_joint_pos']).tolist()}
faces=current_robot_triangles(screen.ik,robot,adapter.xml)
rows=[]
for point in points:
 dist,closest,_=closest_surface(faces,point)
 rows.append({'point':point.tolist(),'robot_visual_surface_distance_m':dist,'nearest_robot_surface_point':closest.tolist(),'held_pixel_distance_m':float(cKDTree(held).query(point)[0]) if len(held) else None})
report={'case':str(a.case),'source':str(a.source),'held_anchor_id':adapter.held,'held_pixel_count':len(held),'held_bounds':[held.min(0).tolist(),held.max(0).tolist()] if len(held) else None,'held_entity':vars(scene.entities[adapter.held]) if adapter.held in scene.entities else None,'source_screen_reason':summary['arms'][0]['stop_reason'],'replayed_screen_reason':verdict.get('reason'),'screen':{k:v for k,v in verdict.items() if k not in ('ik_checks','public_nearby_points')},'collision_samples':rows,'physics_steps':0,'rpc_calls':0,'private_object_coordinates_used':False,'cache_scope':'same frozen public screen inputs; no resegmentation','self_filter':adapter.public_geometry_evidence}
# Compare the same public obstacle samples with actual proprioceptive poses.
actual=json.loads((a.case/'collision_checks_off/execution.json').read_bytes())
robots=[actual['trace'][0]['before'],*[row['after'] for row in actual['trace']]]
comparisons=[]
arm=verdict.get('arm_screen')
if arm:
 from robots.libero.bounded_kernels.ik import BatchedDampedIK
 from robots.libero.v5_grasp_kinematics import robot_link_hulls
 kernel=BatchedDampedIK.from_source(screen.ik)
 q=np.asarray([row['joint_positions_rad'] for row in robots])
 _,_,_,transforms=kernel.forward(q,links=True)
 point=np.asarray(arm['obstacle_point'])
 for hull in robot_link_hulls(screen.ik.reference['path']):
  if hull['name']!=arm['link']:continue
  values=[]
  for transform in transforms[hull['node']]:
   local=(point-transform[:3,3])@transform[:3,:3]
   values.append(float((hull['equations'][:,:3]@local+hull['equations'][:,3]).max()))
  comparisons.append({'link':hull['name'],'actual_halfspace_min_m':min(values),'actual_initial_halfspace_m':values[0],
   'actual_joint_distance_to_predicted_min_rad':float(np.linalg.norm(q-np.asarray(arm['joint_positions_rad']),axis=1).min()),
   'actual_poses':len(robots),'collision_margin_m':.004})
else:
 for group,group_points in verdict.get('public_scene_collision_points',{}).items():
  if not group_points:continue
  box=next(b for b in screen.geometry['boxes'] if b['name']==group)
  for point in group_points:
   values=[]
   for robot in robots:
    local=(np.asarray(point)-robot['eef_xyz_m'])@(Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix())
    opening=screen.opening;screen.opening=robot['gripper_opening_m']
    values.append(float(screen._halfspace_distance(local[None,:],box)[0]));screen.opening=opening
   comparisons.append({'part':group,'point':point,'actual_halfspace_min_m':min(values),'actual_initial_halfspace_m':values[0],
    'actual_poses':len(robots),'collision_margin_m':.004})
report['planned_vs_actual_public_geometry']=comparisons
report['public_screen_input_sha256']=signature.hexdigest()
report['diagnostic_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
with a.output.open('x') as f:json.dump(report,f,indent=2,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v))
print(json.dumps({'output':str(a.output),'reason':verdict.get('reason'),'samples':len(rows),'held_pixels':len(held)}))
