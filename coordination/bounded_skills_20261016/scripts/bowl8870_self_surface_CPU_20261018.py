"""Measure collision pixels against the actual public finger/visual geometry."""
import json,os,sys
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1')
root=Path('/public/home/sunyihan/rpent_libero_eval')
sys.path.insert(0,str(root/'source_bounded_chunk_v3_self_filter_20261018_b6cf6d0'))
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_self_filter import gripper_at_measured_fingers,gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry
base=root/'coordination/bounded_skills_20261016'
report=json.loads((base/'reports/bowl8870_collision_pixels_CPU_20261018.json').read_text())
xml=root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
geometry={**panda_geometry(xml),'visual_boxes':gripper_visual_boxes(str(xml))}
results=[]
for case in report['results']:
 job=case['job'];d=next((root/'results/bounded_skills/feasibility_20261017'/('job'+job)).glob('*oracle*'))
 rows=[json.loads(l) for l in (d/'choices.jsonl').read_text().splitlines()]
 robot=next(detail['execution']['trace'][-1]['after'] for row in reversed(rows[:2])
     for detail in reversed(row['execution_details']) if detail.get('execution',{}).get('trace'))
 assert np.allclose(robot['eef_xyz_m'],rows[2]['request']['robot']['eef_xyz_m'])
 hand=gripper_at_measured_fingers(geometry,robot['finger_positions_m'])
 points=np.asarray(case['points']);site=Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()@Rotation.from_euler('z',-np.pi/2).as_matrix()
 local=(points-robot['eef_xyz_m'])@site
 surfaces=[]
 for kind in ('visual_boxes','boxes'):
  for box in hand[kind]:
   equations=np.asarray(box['convex_halfspaces'])
   surfaces.append(dict(kind=kind,name=box['name'],max_halfspace_distance_m=(local@equations[:,:3].T+equations[:,3]).max(1).tolist()))
 results.append(dict(job=job,points=points.tolist(),robot=robot,local=local.tolist(),surfaces=surfaces))
p=base/'reports/bowl8870_self_surface_CPU_20261018.json'
p.write_text(json.dumps(dict(scope='static gripper geometry and current proprioception only',results=results,controls=0,private_truth_used=False),indent=2)+'\n')
print(json.dumps(results))
