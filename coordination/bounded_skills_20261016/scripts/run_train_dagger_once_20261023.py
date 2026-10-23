"""Measure train-only fixed choices after physically reaching their requested prefix."""
import argparse
import copy
import hashlib
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


def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def checked(reference):
    path=Path(reference['path']);assert ref(path)=={k:reference[k] for k in ('path','sha256')};return path

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded

def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))

def worker(args,plan):
    job=plan['jobs'][args.worker];query=json.loads(checked(job['query']).read_text());source=Path(job['execution_source'])
    assert query['split']=='train' and query['training_admission'] and query['collection_required_under_current_contract']
    sys.path.insert(0,str(source));os.chdir(source)
    os.environ.update(LIBERO_TYPE='standard',LIBERO_CONFIG_PATH=str(checked(plan['libero_config']).parent))
    hooks=module('train_dagger_hooks',source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    hooks.bootstrap_source('original',evaluation='hybrid_repair');hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from scripts import probe_bounded_hybrid_repair as repair
    from robots.libero.bounded_offline_labels import load_annotation_state
    from rpent.skill_package.contract import legal_after
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    producer=module('training_candidate_producer',checked(plan['measurement_producer']))
    assignment=json.loads((args.output/'assignment.json').read_text())
    endpoints={k:HttpRpcClient(assignment[k+'_url']) for k in ('sam3','vla')}
    episode=args.output/'episode';episode.mkdir()
    case=job['case'];world=repair.constructed_original_start(case,plan) if case.get('diagnostic',{}).get('own_layout') else None
    with probe.runtime(case,endpoints,episode,domain='original',constructed_start=world) as (facade,adapter,policy,timings):
        if job['episode_origin'] is not None:
            origin=pickle.loads(checked(job['episode_origin']).read_bytes());physics=origin.get('physics',origin)
            facade.restore(physics);status=facade.goal_status();specs,_=probe.split_subtasks(status['goals'],adapter.ex.instruction)
            facade._episode_initial_grasp_supports={s['source_symbol']:facade.grasp_reference(s['source_symbol']) for s in specs if s['mode']=='pick'}
        snapshot=pickle.loads(checked(query['private_physical_snapshot']).read_bytes())
        if 'physics' in snapshot:
            probe.restore_checkpoint(facade,adapter,policy,snapshot)
            adapter._incremental_previous_robot=None;adapter.refresh()
            restoration={'source':'captured complete runtime','original_physics_sha256':probe.snapshot_digest(snapshot['physics'])}
        else:
            restoration=repair.restore_original_subtask(facade,adapter,policy,{'physics':query['private_physical_snapshot'],
                'annotation':query['private_prefix_annotation_state']})
        original_vla=[c for c in query['public_request']['candidates'] if c['skill']=='call_vla']
        adapter.human_available=False
        adapter.allow_vla=bool(original_vla)
        adapter.vla_options_v2=any('preparation' in c['parameters'] for c in original_vla)
        prefix_request=adapter.request(k=4)
        old_by_id={c['id']:c for c in query['public_request']['candidates']}
        new_by_id={c['id']:c for c in prefix_request['candidates']}
        prefix=list(query['prefix']);reason=None;prefix_receipts=[]
        if prefix:
            for cid in prefix:
                old=old_by_id.get(cid);new=new_by_id.get(cid)
                if old is None or new is None or (old['skill'],old['parameters'])!=(new['skill'],new['parameters']):
                    reason='prefix_option_unavailable_in_actual_reconstruction';break
            if reason is None:
                try:
                    for i,cid in enumerate(prefix):
                        if cid not in legal_after(prefix_request,prefix[:i]):
                            reason='prefix_not_legal_in_actual_reconstruction';break
                except ValueError:reason='prefix_not_legal_in_actual_reconstruction'
            if reason is None:
                decision={k:prefix_request[k] for k in ('schema_version','observation_id','revision')};decision.update(kind='decision',candidate_ids=prefix)
                prefix_receipts=adapter.execute(prefix_request,decision)
                if len(prefix_receipts)!=len(prefix) or any(r['outcome']!='success' for r in prefix_receipts):reason='physical_prefix_not_reached'
        write(args.output/'prefix.json',{'requested':prefix,'request':prefix_request,'receipts':prefix_receipts,'reason':reason,'restoration':restoration})
        if reason is None and (adapter.p.env.terminated or adapter.p.env.truncated):reason='prefix_or_root_native_stop_before_candidate'
        request=adapter.request(k=4) if reason is None else None
        candidate=next((c for c in request['candidates'] if c['id']==query['candidate_id']),None) if request else None
        if reason is None and (candidate is None or candidate['id'] not in legal_after(request,[])):
            reason='selected_option_unavailable_after_actual_prefix'
        if candidate is not None and (candidate['skill'],candidate['parameters'])!=(query['candidate']['skill'],query['candidate']['parameters']):
            raise ValueError('selected public action identity changed')
        contract=copy.deepcopy(query['outcome_contract'])
        if reason is None and contract is None:
            status=facade.goal_status();specs,unsupported=probe.split_subtasks(status['goals'],adapter.ex.instruction)
            if unsupported:reason='registered_original_subgoal_rule_uncovered'
            selected_spec=None
            for spec in specs:
                if status['satisfied'][spec['goal_index']]:continue
                source_entity,_=probe.bind_subtask(policy,adapter,spec)
                if spec['mode']=='pick' and source_entity is not None and adapter.held==source_entity.id:continue
                selected_spec=spec;break
            if selected_spec is None:reason=reason or 'no_remaining_registered_subgoal'
            if reason is None:
                from rpent.skill_package.vla import VLABudget
                from dataclasses import asdict
                contract={'version':'original-subtask-measured/1','subtask':selected_spec,
                    'pick':'private_sustained_grasp_v3_post_branch_window','other_modes':'unchanged_registered_task_predicate',
                    'self_continuation':'bounded oracle until registered subtask or budget',
                    'vla_budget':asdict(adapter.vla_budget), 'full_task_call_vla':'unchanged_native_task_completion; not sustained-grasp truth',
                    'truth_code':ref(source/'robots/libero/v5_grasp_truth.py')}
        if reason is not None:
            write(args.output/'summary.json',{'query_id':query['query_id'],'record_id':query['record_id'],'status':'unknown',
                'reason':reason,'prefix_physically_reached':len(prefix_receipts)==len(prefix) and all(r['outcome']=='success' for r in prefix_receipts),
                'trials':[],'candidate_measured':False,'training_admission':False,'source_split':'train','case':case,
                'original_query':job['query'],'prefix_evidence':ref(args.output/'prefix.json')})
            return
        contract['truth_code']=ref(source/'robots/libero/v5_grasp_truth.py')
        _,snapshot_ref=probe.save_checkpoint(facade,adapter,policy,args.output/'private_actual_candidate_state.pkl',request)
        revision=json.loads((source/'SOURCE_REVISION.json').read_text())['commit']
        binding={'request_sha256':digest(request),'prefix':[],'snapshot_sha256':snapshot_ref['sha256'],
            'outcome_contract_sha256':digest(contract),'source_revision':revision}
        new_id='original-train-dagger/'+digest({'parent_query':query['query_id'],'binding':binding,'candidate_id':candidate['id']})
        registered={'query_id':new_id,'record_id':new_id,'binding':binding,'snapshot':{k:snapshot_ref[k] for k in ('path','sha256')},
            'public_request':request,'prefix':[],'candidate_id':candidate['id'],'candidate':candidate,
            'outcome_contract':contract,'split':'train','scope_kind':'registered_original_train_dagger',
            'training_admission':True,'evaluation_only':False,'PRO':False,'D2':False,'confirmation':False}
        write(args.output/'registered_candidate.json',registered)
        trial_dir=args.output/'trial0'
        result=producer.evaluate_candidate_at_saved_state(registered,probe,facade,adapter,policy,trial_dir,job['seed'])
        write(args.output/'summary.json',{'query_id':query['query_id'],'new_query_id':new_id,'record_id':new_id,'status':'physical_result',
            'trials':[{'result':result,'summary':ref(trial_dir/'summary.json')}],'candidate':candidate,'case':case,
            'registered_query':ref(args.output/'registered_candidate.json'),'source_split':'train','training_admission':True,
            'requested_repeats':1,'original_query':job['query'],'prefix_evidence':ref(args.output/'prefix.json'),
            'replacement_mapping':{'old_record_id':query['record_id'],'old_query_id':query['query_id'],'old_prefix':query['prefix'],
                'new_record_id':new_id,'new_prefix':[],'reason':'fresh physically reached prefix state and current source; do not copy to old binding'},
            'PRO':False,'D2':False,'confirmation':False})


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',type=int)
    args=p.parse_args();plan=json.loads(args.manifest.read_text())
    assert not plan['training'] and plan['training_split_collection'] and plan['requested_repeats']==1
    if args.worker is not None:return worker(args,plan)
    args.output.mkdir(parents=True,exist_ok=True)
    source=Path(plan['jobs'][0]['execution_source']);sys.path.insert(0,str(source));os.chdir(source);os.environ['PYTHONPATH']=str(source)
    os.environ['LIBERO_CONFIG_PATH']=str(checked(plan['libero_config']).parent)
    hooks=module('train_services_hooks',source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py');hooks.bootstrap_source('original',evaluation='hybrid_repair')
    from scripts.probe_bounded_feasibility import services
    from scripts.bounded_state_exclusions import check_exclusions
    check_exclusions([j['case'] for j in plan['jobs']],plan['permanent_exclusions'])
    service_output=args.output/f'services_{time.time_ns()}';service_output.mkdir()
    with hooks.owned_services(SimpleNamespace(source=source,output=service_output,sam3_entry=checked(plan['sam_entry'])),services,vla=True) as endpoints:
        def run(index):
            closed=args.output/f'closed_{index:03d}.json'
            if closed.exists():return
            directory=args.output/f'query{index:03d}'
            if directory.exists():directory.rename(args.output/f'interrupted_{index:03d}_{time.time_ns()}')
            directory.mkdir();write(directory/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
            with (directory/'worker.log').open('x') as log:
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--manifest',str(args.manifest),'--output',str(directory),'--worker',str(index)],
                    stdout=log,stderr=subprocess.STDOUT,check=True)
            write(closed,ref(directory/'summary.json'));print(json.dumps({'closed':index}),flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for future in as_completed([pool.submit(run,i) for i in range(len(plan['jobs']))]):future.result()


if __name__=='__main__':main()
