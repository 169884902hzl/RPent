"""Replay the actual public rejection and compare screened shorter prefixes."""
import argparse,copy,hashlib,json,pickle,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--recorded',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.source))
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
x=pickle.loads(a.input.read_bytes());s=x['screen'].rebase_start(x['robot']);r=json.loads(a.recorded.read_bytes())['screen'];at=r['at'];current={'xyz_m':x['robot']['eef_xyz_m'],'quat_xyzw':x['robot']['eef_quat_xyzw']}
actual=s._geometry_at(at)
assert actual['reason']==r['reason'] and actual['counts']==r['counts'] and actual['target_counts']==r['target_counts']
rows=[]
for scale in [1.,.5,.25]:
 screen=copy.deepcopy(s);goal=copy.deepcopy(x['waypoints'][-1]);goal['xyz_m']=(np.array(current['xyz_m'])+(np.array(goal['xyz_m'])-current['xyz_m'])*scale).tolist()
 verdict=screen([current,goal]);rows.append({'distance_m':float(np.linalg.norm(np.array(goal['xyz_m'])-current['xyz_m'])),'result':verdict})
hits=[]
for box,points in actual['public_scene_collision_points'].items():
 b=next(b for b in s.geometry['boxes'] if b['name']==box)
 for point in points:
  hit=np.array(point)
  def gap(pose):
   site=Rotation.from_quat(pose['quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix();return float(s._halfspace_distance(((hit-pose['xyz_m'])@site).reshape(1,3),b)[0])
  hits.append({'hand_part':box,'xyz_m':point,'initial_gap_m':gap(current),'rejected_gap_m':gap(at),'distance_to_target_surface_m':float(cKDTree(s.target).query(hit)[0]),'initial_occupied_points':len(s.initial_margin.get(box,{}))})
result={'scope':'CPU public geometry replay; no physics, no new SAM, no private coordinates','input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'actual_rejection_reproduced':True,'hits':hits,'prefixes':rows,'collision_clearance_unchanged_m':.004}
a.output.write_text(json.dumps(result,indent=2));print(json.dumps({'hits':hits,'prefixes':[(r['distance_m'],r['result']['passed'],r['result']['reason']) for r in rows]}))
