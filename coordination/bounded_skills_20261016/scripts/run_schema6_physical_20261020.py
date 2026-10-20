"""Resumable schema6 developer probes, one independent episode process at a time."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))


def hooks(source):
    path=source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec=importlib.util.spec_from_file_location('schema6_hooks',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def checked(ref):
    path=Path(ref['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError(f'registered input changed: {path}')
    return path


def worker(args, plan):
    row=plan['jobs'][args.worker]
    os.environ['LIBERO_TYPE']='pro' if row['kind']=='d2' else 'standard'
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS']=str(args.output/'private_grasp_models')
    helper=hooks(args.source);helper.bootstrap_source('d2')
    helper.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    assignment=json.loads((args.output/'assignment.json').read_bytes())
    endpoints={key:HttpRpcClient(assignment[key+'_url']) for key in ('sam3','vla')}
    helper.install_d2_request_compatibility(probe)
    if row['kind']=='d2':
        manifest=json.loads(checked(row['manifest']).read_bytes())
        manifest['recovery_budget']=row['recovery_budget']
        manifest['source_commit']=plan['source_commit']
        manifest['schema_version']=plan['schema_version']
        manifest['parent_registration']=row['manifest']
        result=probe.evaluate_case(row['case'],endpoints,args.output/'episode',manifest,startup=args.startup)
    elif row['kind']=='drawer':
        from robots.libero.bounded_oracle import NoPublicOption
        with probe.runtime(row['case'],endpoints,args.output/'episode',domain='original') as (facade,adapter,policy,timings):
            adapter.allow_vla=False
            common,common_ref=probe.save_checkpoint(facade,adapter,policy,args.output/'private_common.pkl')
            arms=[]
            for arm in ('nudge','guarded'):
                probe.restore_checkpoint(facade,adapter,policy,common)
                adapter.guarded_move_v1=arm=='guarded'
                trace=[];started=time.perf_counter()
                initial=probe.snapshot_digest(facade.snapshot())
                while len(trace)<160 and not (adapter.p.env.terminated or adapter.p.env.truncated):
                    request=adapter.request(k=4)
                    try: decision=policy.choose(request)
                    except NoPublicOption: break
                    before=len(adapter.details)
                    receipts=adapter.execute(request,decision)
                    trace.append({'request':request,'decision':decision,'receipts':receipts,'details':adapter.details[before:]})
                    with (args.output/(arm+'_choices.jsonl')).open('a') as stream:
                        stream.write(json.dumps(trace[-1],default=str)+'\n')
                    if any(r['skill'] in {'finish','ask_help'} for r in receipts):break
                    if args.startup and any(r['steps_used']>0 for r in receipts):break
                arms.append({'arm':arm,'success':bool(facade.goal_status()['done']),'decisions':len(trace),
                    'sim_steps':adapter.p.env.execution_budget()['used_sim_steps'],
                    'wall_s':time.perf_counter()-started,'initial_physics_sha256':initial,
                    'max_actions_per_decision':max((len(r['receipts']) for r in trace),default=0)})
            result={'case':row['case'],'arms':arms,'common':common_ref,
                'status':'startup_physical' if args.startup else 'physical_result',
                'sim_steps':sum(a['sim_steps'] for a in arms),
                'timings':timings.summary(time.perf_counter()-timings.started),'training':False}
    else:
        from scripts.probe_bounded_hybrid_repair import restore_original_subtask
        from rpent.skill_package.contract import legal_after
        saved=row['position'];case=row['case']
        with probe.runtime(case,endpoints,args.output/'episode',domain='original') as (facade,adapter,policy,timings):
            adapter.allow_vla=False
            restored=restore_original_subtask(facade,adapter,policy,
                {'physics':saved['snapshot'],'annotation':saved['annotation_state']})
            request=adapter.request(k=4)
            common,common_ref=probe.save_checkpoint(facade,adapter,policy,args.output/'private_common.pkl',request)
            specs,unsupported=probe.split_subtasks(facade.goal_status()['goals'],adapter.ex.instruction)
            source_id=saved['candidate']['parameters']['anchor_id']
            spec=None
            for subtask in specs:
                bound,_=probe.bind_subtask(policy,adapter,subtask)
                if (bound is not None and bound.id==source_id
                        and not facade.goal_status()['satisfied'][subtask['goal_index']]):
                    spec=subtask
                    break
            arms=[]
            for arm in ('default','original_variant'):
                directory=args.output/arm;directory.mkdir()
                probe.restore_checkpoint(facade,adapter,policy,common)
                current=copy.deepcopy(request)
                if arm=='default':
                    candidate=next((c for c in current['candidates'] if c['skill']=='move_to'
                        and c['parameters']=={'anchor_id':source_id}),None)
                else:
                    candidate=adapter._candidate('move_to',saved['candidate']['parameters'])
                    if candidate is not None:current['candidates'].append(candidate)
                adapter.latest_request=current
                initial=probe.snapshot_digest(facade.snapshot());started=time.perf_counter()
                if candidate is None or candidate['id'] not in legal_after(current,[]):
                    arms.append({'arm':arm,'status':'public_option_unavailable','success':None,
                        'initial_physics_sha256':initial});continue
                decision={key:current[key] for key in ('schema_version','observation_id','revision')}
                decision.update(kind='decision',candidate_ids=[candidate['id']])
                receipts=adapter.execute(current,decision)
                write(directory/'first_action.json',{'request':current,'decision':decision,'receipts':receipts,
                    'execution_details':adapter.details})
                continuation=None
                if spec is not None and not args.startup:
                    successor=adapter.request(k=4)
                    continuation,_=probe.trial(facade,adapter,policy,timings,spec,'self',
                        11400000+args.worker*1000,directory/'continuation',successor,decision_limit=159)
                arms.append({'arm':arm,'status':'physical_result','initial_physics_sha256':initial,
                    'success':continuation['success'] if continuation else None,
                    'first_receipts':receipts,'continuation':continuation,'wall_s':time.perf_counter()-started})
            result={'position':saved,'restoration':restored,'common_state':common_ref,'subtask':spec,
                'unsupported':unsupported,'arms':arms,'training':False,
                'status':'startup_physical' if args.startup else 'physical_result'}
    write(args.output/'summary.json',result)
    if args.startup:
        # Real requests, not imports, are required. Native completion is also
        # a physical result, never a reason to forge a successful receipt.
        import glob
        steps = (result.get('sim_steps',0) or sum(t.get('sim_steps',0) for t in result.get('trials',[]))
            or sum(r['steps_used'] for arm in result.get('arms',[]) for r in arm.get('first_receipts',[])))
        if steps <= 0:
            raise RuntimeError('startup produced no physical execution evidence')
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',type=int)
    p.add_argument('--startup',action='store_true')
    p.add_argument('--startup-only',action='store_true')
    p.add_argument('--preflight',action='store_true')
    args=p.parse_args();args.source=args.source.resolve(strict=True)
    args.manifest=args.manifest.resolve(strict=True);sys.path.insert(0,str(args.source))
    plan=json.loads(args.manifest.read_bytes())
    if plan['training'] or plan['schema_version']!='bounded-skills/6':raise ValueError('wrong evaluation registration')
    if args.worker is not None:return worker(args,plan)
    for row in plan['jobs']:
        for key in ('bddl','grasp_measurement_calibration'):
            if key in row['case']:checked(row['case'][key])
        if 'manifest' in row:checked(row['manifest'])
        if 'position' in row:
            for key in ('snapshot','annotation_state'):checked(row['position'][key])
    if args.preflight:
        print(json.dumps({'preflight':'passed','jobs':len(plan['jobs'])}));return 0
    os.environ['PYTHONPATH']=str(args.source);os.chdir(args.source)
    helper=hooks(args.source);helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    args.output.mkdir(parents=True,exist_ok=True)
    service_args=SimpleNamespace(source=args.source,output=args.output,
        sam3_entry=Path(plan['sam_entry']['path']))
    checked(plan['sam_entry'])
    with helper.owned_services(service_args,services,vla=True) as endpoints:
        for index,row in enumerate(plan['jobs']):
            directory=args.output/f'case{index:03d}'
            closed=args.output/f'closed_{index:03d}.json'
            prior=[directory/'summary.json',*args.output.glob(f'case{index:03d}_attempt*/summary.json')]
            completed=next((path for path in prior if path.exists()),None)
            if closed.exists() or completed is not None:
                if not closed.exists():write(closed,{'summary':str(completed)})
                continue
            if directory.exists():
                attempt=1
                while (args.output/f'case{index:03d}_attempt{attempt}').exists():attempt+=1
                directory=args.output/f'case{index:03d}_attempt{attempt}'
            if index==0:
                startup=args.output/f'startup_{int(time.time())}';startup.mkdir()
                write(startup/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
                command=[sys.executable,str(Path(__file__).resolve()),'--source',str(args.source),
                    '--manifest',str(args.manifest),'--output',str(startup),'--worker',str(index),'--startup']
                with (startup/'worker.log').open('x') as stream:
                    subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
                if args.startup_only:
                    print(json.dumps({'startup':'physical_passed','proof':str(startup/'summary.json')}),flush=True)
                    return 0
            directory.mkdir()
            write(directory/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
            command=[sys.executable,str(Path(__file__).resolve()),'--source',str(args.source),
                '--manifest',str(args.manifest),'--output',str(directory),'--worker',str(index)]
            with (directory/'worker.log').open('x') as stream:
                subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
            write(closed,{'summary':str(directory/'summary.json'),
                'sha256':hashlib.sha256((directory/'summary.json').read_bytes()).hexdigest()})
            print(json.dumps({'index':index,'closed':str(directory/'summary.json')}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
