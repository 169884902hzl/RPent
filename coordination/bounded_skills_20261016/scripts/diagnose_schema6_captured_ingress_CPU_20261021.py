# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Replay public planning from an owned capture; no simulator or RPC."""
import argparse,json,pickle,hashlib,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--episode',type=Path,required=True);p.add_argument('--anchor',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.source.resolve(strict=True)))
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_runtime import MeasuredScene
saved=pickle.loads(a.checkpoint.read_bytes());runtime=saved['public_runtime']
a.output.mkdir(exist_ok=False,parents=True)
class Depth:
 latest_step=0
 def path(self,name):return a.episode/name/('00'+Path(name).suffix)
 def load(self,name):
  path=self.path(name)
  if path.suffix=='.npz':
   with np.load(path) as v:return v['array']
  if path.suffix=='.json':return json.loads(path.read_bytes())
  import imageio.v3 as iio
  return iio.imread(path)
 def load_bytes(self,name):return self.path(name).read_bytes()
 def exists(self,name,**kwargs):return self.path(name).exists()
 def save(self,name,value,**kwargs):
  path=self.artifact_path(name,**kwargs);np.savez_compressed(path,array=value);return path
 def artifact_path(self,name,**kwargs):return a.output/name
class NoRPC:
 def call(self,*args,**kwargs):raise AssertionError(f'CPU capture must not call RPC: {args}')
state=Depth();scene=object.__new__(MeasuredScene);scene.__dict__.update(runtime['scene']);scene.toolkit=SimpleNamespace(_state=state);scene.rpc=NoRPC()
raw=saved['physics']['actuator_state']['observation_state']['cache']
cache={key:raw[key] for key in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_joint_pos')}
env=SimpleNamespace(raw_obs=lambda:cache,execution_budget=lambda:{'remaining_sim_steps':10000,'used_sim_steps':0},terminated=False,truncated=False)
adapter=object.__new__(MeasuredSkillAdapter);adapter.__dict__.update(runtime['adapter']);adapter.scene=scene;adapter.p=SimpleNamespace(env=env);adapter.ex=SimpleNamespace(toolkit=scene.toolkit,instruction=scene.instruction)
adapter.record_public_geometry=False
adapter._has_anchor=lambda e:e is not None and e.id==a.anchor
request=adapter.request(k=1)
result=adapter._candidate('move_to',{'anchor_id':a.anchor},complete=True)
summary={'checkpoint_sha256':hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),'anchor':a.anchor,'plan':adapter.plans.get(a.anchor),'selected':result,'diagnostics':adapter.candidate_diagnostics,'rpc_calls':0,'physics_steps':0}
(a.output/'summary.json').write_text(json.dumps(summary,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v),indent=2))
for d in adapter.candidate_diagnostics:
 if d.get('stage')=='move_variant_resolution':
  print(json.dumps(d),flush=True)
print('plan',str(adapter.plans.get(a.anchor))[:1000]);print('result',result)
