"""Run registered five-trial panels with frozen state, explicit feedback and budgets."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace


def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def ref(path):
    import hashlib
    path=Path(path);return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(value):
    path=Path(value['path']);assert ref(path)['sha256']==value['sha256'],path;return path


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v))


class EpisodeWallBudget(Exception):
    """The registered wall budget stops further simulator controls."""


def run_line(args, plan, row, line, probe, facade, adapter, policy, timings, checkpoint):
    from robots.libero.bounded_success_loop import enable, choose, native_success
    from rpent.skill_package.feedback import TaskAlreadySucceeded
    from rpent.skill_package.vla import VLABudget
    from robots.libero.bounded_async import http_choice
    probe.restore_checkpoint(facade,adapter,policy,checkpoint)
    initial=probe.snapshot_digest(facade.snapshot());assert initial==probe.snapshot_digest(checkpoint['physics'])
    initial_steps=adapter.p.env.execution_budget()['used_sim_steps']
    directory=args.output/line;directory.mkdir()
    adapter.permissive_preparation_options=True
    adapter.adaptive_contact_skills=True
    adapter.verify_instance_class_v10=True
    adapter.route_failure_feedback=bool(plan.get('route_failure_feedback'))
    enable(adapter,facade,level_b=False)
    if plan.get('own_contact_only',False):adapter.allow_vla=False
    adapter.vla_budget=VLABudget(**plan['vla_budget'])
    original=adapter.p.model
    adapter.p.model=probe.SeededPolicy(original,row['policy_seed'],input_ledger=directory/'vla_inputs.jsonl')
    seed_model=adapter.p.model
    event_start=len(timings.events);started=time.perf_counter();decisions=0
    reason='decision_budget';records=[]
    def check_wall():return time.perf_counter()-started>=plan['budget']['wall_s']
    original_step=adapter.p._step_env
    def bounded_step(action):
        if check_wall():raise EpisodeWallBudget()
        return original_step(action)
    adapter.p._step_env=bounded_step
    try:
        with (directory/'choices.jsonl').open('x') as stream:
            for index in range(plan['budget']['decisions']):
                if check_wall():reason='wall_budget';break
                if adapter.p.env.truncated or adapter.p.env.execution_budget()['remaining_sim_steps']<=0:
                    reason='environment_budget';break
                decision_event_start=len(timings.events);cycle_start=time.perf_counter()
                try:
                    with timings.measure('planning.request'):
                        request=adapter.request(k=1)
                except TaskAlreadySucceeded:
                    reason='native_task_success_before_decision';break
                if check_wall():reason='wall_budget';break
                if (plan.get('collect_failure_history',False) and line=='model'
                        and row['panel']=='development' and records
                        and any(r['outcome'] in {'failure','rejected','no_effect'}
                            for r in records[-1]['receipts'])):
                    from rpent.skill_package.contract import legal_after
                    legal=legal_after(request,[])
                    if len(legal)>=2:
                        history=directory/'failure_history'/f'decision_{index:03d}'
                        history.mkdir(parents=True)
                        with timings.measure('collection.failure_history'):
                            _,state=probe.save_checkpoint(facade,adapter,policy,history/'complete.pkl',request=request)
                            from robots.libero.bounded_offline_labels import capture_annotation_state,save_annotation_state
                            annotation=save_annotation_state(history/'annotation.pkl',capture_annotation_state(policy,request))
                            save(history/'position.json',{'world_id':row['world_id'],
                                'panel_task_id':row['panel_task_id'],'source_split':'train',
                                'source_commit':plan['source_commit'],'decision_index':index,
                                'checkpoint':state,'annotation':annotation,'request':request,
                                'previous_receipts':records[-1]['receipts'],'legal':legal,
                                'training_admission':False,'needs_measured_alternatives':2})
                with timings.measure('decision.'+line):
                    if line=='model':
                        service=plan['model_service']
                        def response(value):
                            with (directory/'model_responses.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
                        decision=http_choice(service['endpoint'],on_response=response)(request)
                        selection={'selector':'registered_model_HTTP','adapter_sha256':service['adapter_sha256'],'oracle_called':False}
                    else:
                        decision,selection=choose(probe,facade,adapter,policy,request,only_pi=line=='pi')
                if decision is None:
                    reason='no_legal_option';break
                if check_wall():reason='wall_budget';break
                detail_start=len(adapter.details)
                execution_start=time.perf_counter()
                try:
                    with timings.measure('execution.skill'):
                        receipts=adapter.execute(request,decision)
                except EpisodeWallBudget:
                    reason='wall_budget'
                    stream.write(json.dumps({'index':index,'request':request,'decision':decision,
                        'stop_reason':'wall_budget','receipts':[],
                        'executed_sim_steps':adapter.p.env.execution_budget()['used_sim_steps']-initial_steps})+'\n')
                    stream.flush();decisions+=1;break
                decisions+=1
                record={'index':index,'request':request,'decision':decision,'selector':selection,
                    'receipts':receipts,'details':adapter.details[detail_start:],
                    'execution_wall_s':time.perf_counter()-execution_start,
                    'timing':timings.summary(time.perf_counter()-cycle_start,start_event=decision_event_start)}
                stream.write(json.dumps(record,default=lambda v:v.tolist() if hasattr(v,'tolist') else str(v))+'\n');stream.flush()
                records.append({k:v for k,v in record.items() if k not in {'request','details'}})
                if adapter.p.env.terminated:reason='native_success_during_execution';break
        success=native_success(facade)
        elapsed=time.perf_counter()-started
        result={'panel_task_id':row['panel_task_id'],'world_id':row['world_id'],'category':row['category'],
            'panel':row['panel'],'line':line,'case':row['case'],'level':row['level'],
            'status':'physical_result','success':success,'stop_reason':reason,'decisions':decisions,
            'sim_steps':adapter.p.env.execution_budget()['used_sim_steps']-initial_steps,
            'wall_s':elapsed,'timing':timings.summary(elapsed,start_event=event_start),
            'initial_physics_sha256':initial,'policy_seed':row['policy_seed'],
            'source_commit':plan['source_commit'],'schema_version':adapter.schema_version,
            'budget':plan['budget'],'vla_budget':plan['vla_budget'],'feedback':{'task_success':True,'subgoal_status':False},
            'human_available':False,'cross_episode_memory':False,'training':False,
            'route_failure_feedback':adapter.route_failure_feedback,'model_service':plan.get('model_service') if line=='model' else None,
            'choices':ref(directory/'choices.jsonl')}
        save(directory/'summary.json',result);return result
    finally:
        adapter.p.model=original
        adapter.p._step_env=original_step


def worker(args, plan):
    row=plan['jobs'][args.worker]
    os.environ['LIBERO_TYPE']='pro' if row['panel']=='pro_measurement' else 'standard'
    os.environ['LIBERO_CONFIG_PATH']=str(checked(row['libero_config']).parent)
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS']=str(args.output/'private_grasp_models')
    sys.path.insert(0,str(args.source))
    hooks=load(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py','tier_hooks')
    hooks.bootstrap_source('d2' if row['panel']=='pro_measurement' else 'original',evaluation='hybrid_repair')
    hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    if row['panel']=='pro_measurement':
        from robots.libero.bounded_hybrid_diagnostic import pro_development_session
        probe.d2_session=pro_development_session
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    assignment=json.loads((args.output/'assignment.json').read_bytes())
    endpoints={key:HttpRpcClient(assignment[key+'_url']) for key in ('sam3','vla')}
    episode=args.output/'episode';episode.mkdir()
    from scripts.probe_bounded_hybrid_repair import constructed_original_start
    constructed=constructed_original_start(row['case'],plan) if 'own_layout' in row['case'].get('diagnostic',{}) else None
    with probe.runtime(row['case'],endpoints,episode,domain='d2' if row['panel']=='pro_measurement' else 'original',constructed_start=constructed) as (facade,adapter,policy,timings):
        common=Path(plan['common_starts'])/(row['world_id']+'.pkl')
        common.parent.mkdir(parents=True,exist_ok=True)
        if common.exists():checkpoint=pickle.loads(common.read_bytes())
        elif row.get('initial_snapshot'):
            checkpoint=pickle.loads(checked(row['initial_snapshot']).read_bytes())
            common.write_bytes(pickle.dumps(checkpoint,protocol=5))
        else:
            checkpoint,_=probe.save_checkpoint(facade,adapter,policy,common)
        rows=[]
        for line in row['lines']:
            rows.append(run_line(args,plan,row,line,probe,facade,adapter,policy,timings,checkpoint))
        save(args.output/'summary.json',{'world_id':row['world_id'],'results':rows,'common':ref(common)})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','manifest','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--worker',type=int);a=p.parse_args();a.source=a.source.resolve()
    plan=json.loads(a.manifest.read_bytes());assert plan['budget']=={'decisions':40,'sim_steps':10000,'wall_s':7200}
    assert plan['vla_budget']['blocks']==104 and plan['vla_budget']['max_controls']==520
    if a.worker is not None:return worker(a,plan)
    a.output.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(a.source))
    helper=load(a.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py','tier_launch')
    helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    service_args=SimpleNamespace(source=a.source,output=a.output,sam3_entry=checked(plan['sam_entry']))
    os.environ['PYTHONPATH']=str(a.source);os.chdir(a.source)
    with helper.owned_services(service_args,services,vla=True) as endpoints:
        def run(index):
            closed=a.output/f'closed_{index:03d}.json'
            if closed.exists():checked(json.loads(closed.read_bytes()));return
            directory=a.output/f'case{index:03d}'
            if directory.exists():raise RuntimeError('unfinished worker requires infrastructure attribution before rerun: '+str(directory))
            directory.mkdir();save(directory/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
            command=[sys.executable,str(Path(__file__).resolve()),'--source',str(a.source),'--manifest',str(a.manifest),'--output',str(directory),'--worker',str(index)]
            with (directory/'worker.log').open('x') as stream:subprocess.run(command,check=True,stdout=stream,stderr=subprocess.STDOUT)
            save(closed,ref(directory/'summary.json'))
            from robots.libero.bounded_task_board import update_from_results
            update_from_results(plan['board_root'])
            print(json.dumps({'closed':index}),flush=True)
        with ThreadPoolExecutor(max_workers=plan.get('parallel',8)) as pool:
            for future in as_completed([pool.submit(run,i) for i in range(len(plan['jobs']))]):future.result()


if __name__=='__main__':main()
