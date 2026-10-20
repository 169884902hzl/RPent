"""Cold CPU profiles from exact saved public RGB-D/proprioception, no RPC."""
import argparse
import copy
import cProfile
import hashlib
import json
import pickle
import pstats
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace


class RecordedFrames:
    def __init__(self,root,step):
        self.root,self.latest_step=root,step
    def artifact_path(self,name,*,step=-1):
        return self.root/name/f'{self.latest_step if step==-1 else step:02d}{Path(name).suffix}'
    def load_bytes(self,name):
        return self.artifact_path(name).read_bytes()
    def load(self,name):
        import numpy as np
        import imageio.v2 as imageio
        path=self.artifact_path(name)
        if path.suffix=='.npz':
            with np.load(path) as blob:return blob['array']
        if path.suffix=='.json':return json.loads(path.read_bytes())
        return imageio.imread(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frame-root',type=Path)
    parser.add_argument('--after',action='store_true')
    args=parser.parse_args();args.source=args.source.resolve(strict=True)
    sys.path.insert(0,str(args.source))
    import numpy as np
    from rpent.session import EnvState
    from robots.libero.bounded_skills import MeasuredSkillAdapter
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.skill_package.progress import PublicProgress
    saved=pickle.loads(args.checkpoint.read_bytes());runtime=saved['public_runtime']
    if 'artifact_state' in runtime:
        store=object.__new__(EnvState);vars(store).update(runtime['artifact_state'])
    else:
        if args.frame_root is None:raise ValueError('legacy snapshot requires exact recorded frame root')
        capture=max(e['capture_step'] for a in saved['request']['anchors'] for e in a['evidence'])
        store=RecordedFrames(args.frame_root,capture)
    class NoRPC:
        def call(self,method,*args,**kwargs):
            raise RuntimeError('new segmentation input not present in this CPU snapshot: '+
                str((method,(kwargs.get('kwargs') or {}).get('text_prompt'))))
    scene=object.__new__(MeasuredScene);vars(scene).update(runtime['scene'])
    scene.toolkit=SimpleNamespace(_state=store);scene.rpc=NoRPC()
    if getattr(scene,'rgbd_mask_tracking_v1',False):
        from robots.libero.bounded_mask_tracking import TrackedSegmentation
        history=scene._mask_tracking_history
        scene.rpc=TrackedSegmentation(scene.rpc,store,scene,refresh_captures=None)
        scene._mask_tracking_history=history
    raw=saved['physics']['actuator_state']['observation_state']['cache']
    observed={k:raw[k] for k in ('robot0_eef_pos','robot0_eef_quat','robot0_gripper_qpos','robot0_joint_pos')}
    remaining=(saved.get('request')or{}).get('remaining_sim_steps',10000)
    env=SimpleNamespace(raw_obs=lambda:observed,
        execution_budget=lambda:{'remaining_sim_steps':remaining,'used_sim_steps':10000-remaining},
        terminated=False,truncated=False)
    adapter=object.__new__(MeasuredSkillAdapter);vars(adapter).update(runtime['adapter'])
    restored_defaults=[]
    for name,value in {'_failed_move_anchors':set(),'_move_approach_by_anchor':{},
            '_stationary_observe_modes':set(),'_vla_failed_options':set(),
            'withdrawal_contact':None,'_progress_normals':{},'_progress_goal_directions':{}}.items():
        if not hasattr(adapter,name):
            setattr(adapter,name,value);restored_defaults.append(name)
    for candidate in saved['request']['candidates']:
        anchor=candidate['parameters'].get('anchor_id')
        if anchor and candidate['recent_failures'] and candidate['skill'] in {'move_to','descend','lower'}:
            adapter._failed_move_anchors.add(anchor)
    adapter.scene=scene;adapter.p=SimpleNamespace(env=env)
    vars(adapter.p).update(runtime.get('primitive',{}))
    adapter.ex=SimpleNamespace(toolkit=scene.toolkit,instruction=scene.instruction)
    adapter.record_public_geometry=adapter.allow_vla=False
    adapter._base_geometry=adapter._base_geometry_cache=None
    adapter._screen_cache={};adapter._instance_cache={};adapter._self_filtered_capture=None
    adapter._grasp_geometry_cache={};adapter.plans={};adapter.committed_grasps={}
    adapter.candidate_diagnostics=[];adapter.public_geometry_evidence={}
    adapter.public_progress=PublicProgress(11)
    if args.after:
        adapter.schema6_v1=adapter.lazy_planning_v1=adapter.rendered_self_filter_v1=True
        adapter.verify_instance_crops_v1=False  # New crop logits are not in old CPU captures.
        adapter._capture_obstacles=None
    args.output.mkdir(parents=True,exist_ok=False)
    summary={'checkpoint':str(args.checkpoint),'checkpoint_sha256':hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        'source':str(args.source),'after':args.after,'physics_steps':0,'rpc_calls':0,
        'legacy_runtime_defaults':restored_defaults,
        'source_files':{str(path.relative_to(args.source)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((args.source/'robots/libero').glob('*.py'))},
        'scope':'saved-frame cold CPU computation; no new capture/SAM/control, not N1 latency','stages':{}}
    for name,function in [('capture_obstacles',lambda:adapter._cloud_and_ik()),
                           ('request',lambda:adapter.request(k=4))]:
        profile=cProfile.Profile();begin=time.perf_counter();result=None;error=None;error_trace=None
        try:result=profile.runcall(function)
        except Exception as exc:error=repr(exc);error_trace=traceback.format_exc()
        elapsed=time.perf_counter()-begin;profile.dump_stats(str(args.output/(name+'.pstats')))
        stats=pstats.Stats(profile)
        top=sorted(stats.stats.items(),key=lambda row:row[1][3],reverse=True)[:20]
        entry={'wall_s':elapsed,'error':error,'traceback':error_trace,'top20':[dict(file=k[0],line=k[1],function=k[2],
            primitive_calls=v[0],calls=v[1],self_s=v[2],cumulative_s=v[3]) for k,v in top]}
        if isinstance(result,dict):
            raw_result=json.dumps(result,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v),
                sort_keys=True,separators=(',',':')).encode()
            (args.output/(name+'_result.json')).write_bytes(raw_result)
            entry['result_sha256']=hashlib.sha256(raw_result).hexdigest()
            entry['candidates']=len(result.get('candidates',[]))
        summary['stages'][name]=entry
        print(name,elapsed,error,flush=True)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if any(stage['error'] for stage in summary['stages'].values()):
        raise RuntimeError('saved request profiling failed; inspect retained summary')


if __name__=='__main__':main()
