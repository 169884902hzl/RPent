from pathlib import Path
from types import SimpleNamespace
import json,ast
import numpy as np
from robots.libero.v5_fixture_parts import measured_drawer_faces

r=Path('results/harness_v5/drawer563_public_frame_CPU_20261006')
d=json.loads((r/'t0s10_public_geometry_bundle.json').read_text())
parent,part=(SimpleNamespace(**d['public']['before'][k]) for k in ['parent','part'])
raw=d['public']['before']['raw_metrology']
front=-np.asarray(raw['moving']['normal_xy'])
if np.dot(front,np.asarray(part.xyz)[:2]-np.asarray(parent.xyz)[:2])<0:front=-front
print('public normal oriented by measured drawer relative to measured parent',front)
s=(r/'baseline_fixture_parts.py').read_text();tree=ast.parse(s);f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='measured_drawer_faces');src=ast.get_source_segment(s,f)
variants={'baseline':src,'expand_frame_depth':src.replace('(depth >= edge - .025)', '(depth >= np.min(corners @ front) - .025)').replace('bins = np.arange(edge - .031, edge + .356, .004)','bins = np.arange(np.min(corners @ front) - .031 if key == "frame" else edge - .031, edge + .356, .004)'), 'expand_both_depth':src.replace('(depth >= edge - .025)', '(depth >= np.min(corners @ front) - .025)').replace('(depth >= edge - .03)', '(depth >= np.min(corners @ front) - .03)').replace('bins = np.arange(edge - .031, edge + .356, .004)','bins = np.arange(np.min(corners @ front) - .031, edge + .356, .004)')}
arrays=[]
for i,ref in enumerate(d['RGBD_refs']):
 file=np.load(r/f'world_{i}.npz');arrays.append(file[file.files[0]])
rows=[]
for variant,source in variants.items():
 namespace={'np':np,'Entity':SimpleNamespace};exec(source,namespace)
 for phase,indices in [('before',[0,1]),('after',[2,3])]:
  current_data=d['public'][phase]['current_moving_part'];current=SimpleNamespace(**current_data) if current_data else None
  for view,world in [('agentview',arrays[indices[0]]),('wrist',arrays[indices[1]]),('fused',np.concatenate([arrays[j].reshape(-1,3) for j in indices]))]:
   fit,clouds=namespace['measured_drawer_faces'](world,parent,part,front,moving_part=current)
   row={'variant':variant,'phase':phase,'view':view,'frame':fit.get('frame'),'moving':fit.get('moving'),'points':fit.get('point_counts'),'current_binding_available':current is not None};rows.append(row)
   print(variant,phase,view,'frame',row['frame']['centre'] if row['frame'] else None,'moving',row['moving']['centre'] if row['moving'] else None)
(r/'depth_window_sensitivity.json').write_text(json.dumps({'scope':'Public CPU sampling hypothesis only; no verdict changes, runtime changes or private labels','inferred_axis_not_original_serialized_axis':front.tolist(),'rows':rows},indent=2)+'\n')
