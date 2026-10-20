"""M7: regenerate rule labels along new schema6 prefixes from saved originals."""
import argparse
import copy
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--windows',type=Path,required=True)
    p.add_argument('--registry',type=Path,required=True)
    p.add_argument('--parent-index',type=Path,
        help='C2 frozen 2414-position inventory and unchanged task/initial-state splits')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source-revision',required=True)
    p.add_argument('--shard',type=int,default=0)
    p.add_argument('--shards',type=int,default=1)
    p.add_argument('--limit-requests',type=int)
    a=p.parse_args();a.source=a.source.resolve(strict=True)
    for name in ('robots/libero/bounded_offline_labels.py','rpent/skill_package/schema.json'):
        if not (a.source/name).is_file():raise FileNotFoundError(a.source/name)
    sys.path.insert(0,str(a.source))
    from robots.libero.bounded_offline_labels import (
        annotate_prefix,load_annotation_state,rebuild_schema6_captured_request,
        rebuild_saved_public_screens,save_annotation_state)
    from rpent.skill_package.contract import legal_after,is_boundary
    from rpent.skill_package.progress import PublicProgress,DEFAULT_STAGNANT_DECISIONS
    from scripts.bounded_state_exclusions import check_exclusions
    data=json.loads(gzip.decompress(a.windows.read_bytes()))
    if len(data['episodes'])!=220 or data['errors']:raise ValueError('original220 source is incomplete')
    if not 0<=a.shard<a.shards:raise ValueError('invalid CPU shard')
    source_paths=['robots/libero/bounded_skills.py','robots/libero/bounded_screen.py',
        'robots/libero/bounded_offline_labels.py','robots/libero/bounded_goal_progress.py',
        'robots/libero/bounded_oracle.py','robots/libero/v5_oracle_policy.py',
        'rpent/skill_package/schema.json','rpent/skill_package/contract.py','rpent/skill_package/progress.py']
    files={name:sha((a.source/name).read_bytes()) for name in source_paths}
    outcome=sha(canonical({name:files[name] for name in source_paths if 'oracle' in name}))
    registry={'path':str(a.registry),'sha256':sha(a.registry.read_bytes())}
    parent_index=json.loads(a.parent_index.read_bytes()) if a.parent_index else None
    if parent_index and parent_index['baseline_usable_positions']!=2414:
        raise ValueError('unexpected M7 comparison inventory')
    a.output.mkdir(parents=True,exist_ok=False)
    counts=Counter();categories={};errors=[];excluded=[];started=time.perf_counter();cpu_started=time.process_time()
    with (a.output/'positions.jsonl').open('x',buffering=1) as output:
        for episode in data['episodes'][a.shard::a.shards]:
            case=episode['case']
            if case['episode']['suite'] not in {'libero_spatial','libero_object','libero_goal','libero_10','libero_90'}:
                raise ValueError('PRO/D2 is forbidden for M7')
            try:check_exclusions([case],registry)
            except ValueError as exc:
                excluded.append({'case':case['name'],'reason':str(exc)});continue
            raw=Path(episode['choices_meta']['path']).read_bytes()
            if sha(raw)!=episode['choices_meta']['sha256']:raise ValueError('old original choices changed')
            monitor=PublicProgress(DEFAULT_STAGNANT_DECISIONS);normals={};stationary=set()
            category_counts=categories.setdefault(episode['category'],Counter())
            for line_index,line in enumerate(raw.splitlines(),1):
                row=json.loads(line)
                if 'request' not in row:continue
                reference=row.get('private_prefix_annotation_state')
                if not reference:
                    errors.append({'case':case['name'],'line':line_index,'error':'saved annotation missing'});continue
                try:
                    parent_id=f'original220/{case["name"]}/{row["index"]}'
                    parent=parent_index['parents'][parent_id] if parent_index else None
                    if parent and parent['private_prefix_annotation_state']['sha256']!=reference['sha256']:
                        raise ValueError('parent inventory and original annotation refer to different states')
                    saved=load_annotation_state(reference['path'],reference['sha256'])
                    adapter=saved['adapter']
                    adapter.allow_vla=True
                    adapter.vla_options_v2=False  # Three-consumer synchronization is pending.
                    adapter.verify_instance_crops_v1=False  # No new RGB/SAM inference in M7.
                    adapter._stationary_observe_modes=stationary.copy()
                    geometry=rebuild_saved_public_screens(adapter)
                    for key,plan in adapter.plans.items():
                        normal=(plan.get('handle_measurement',{}).get('pose') or {}).get('approach_normal_xyz')
                        if normal is not None:normals.setdefault(key,normal)
                    state,request,migration=rebuild_schema6_captured_request(saved,row['request'],
                        progress=monitor,progress_normals=normals)
                    current=state['adapter'];monitor=copy.deepcopy(current.public_progress)
                    normals=copy.deepcopy(current._progress_normals)
                    root=a.output/f'state_{counts["requests"]:06d}.pkl.gz'
                    snapshot=save_annotation_state(root,state)
                    counts['requests']+=1;category_counts['requests']+=1
                    prefix=[]
                    for position in range(request['max_actions']):
                        label=annotate_prefix(state,request,prefix)
                        legal=list(legal_after(request,prefix))
                        unknown=[c['id'] for c in request['candidates']
                            if c['id'] in legal and c['skill']=='call_vla']
                        acceptable=[cid for cid in label['rule_acceptable'] if cid not in unknown]
                        binding={'request_sha256':state['request_sha256'],'prefix':prefix.copy(),
                            'snapshot_sha256':snapshot['sha256'],'outcome_contract_sha256':outcome,
                            'source_revision':a.source_revision}
                        record={'record_id':f'M7:{case["name"]}:{row["index"]}:{position}',
                            'parent_record_id':parent_id,'source_parent':parent,
                            'episode':case,'category':episode['category'],'public_request':request,
                            'prefix':prefix.copy(),'binding':binding,'legal':legal,'acceptable':acceptable,
                            'rule_acceptable':acceptable,'measured_success':[],'measured_failure':[],
                            'judge':label['judge'],
                            'selected':label['selected'] if label['selected'] in acceptable else None,
                            'unknown_candidate_ids':unknown,'source_rule_result':label,
                            'snapshot':snapshot,'source_snapshot':reference,'source_line':line_index,
                            'source_choices':episode['choices_meta'],'geometry_reconstruction':geometry,
                            'catalog_migration':migration,'origin_episode_success':episode['success'],
                            'label_type':'conditional_private_rule; not measured branch success',
                            'prefix_origin':'new_schema6_oracle_prediction; never old ID-prefix certification',
                            'pro':False,'confirmation':False,'training':False,
                            'split':'preserve_existing_task_and_initial_state_split_at_C2_join',
                            'physics_steps':0,'rpc_calls':0,'new_vla_candidate_labels':'unknown_until_measured'}
                        output.write(canonical(record).decode()+'\n')
                        counts['positions']+=1;category_counts['positions']+=1
                        effective=bool(acceptable) and len(acceptable)<len(legal) and len(request['candidates'])<=94
                        counts['effective_positions']+=effective;category_counts['effective_positions']+=effective
                        eligible=bool(parent and parent['status']=='ok' and effective)
                        counts['source_eligible_effective_positions']+=eligible
                        category_counts['source_eligible_effective_positions']+=eligible
                        counts['unknown_vla_options']+=len(unknown)
                        selected=record['selected']
                        if selected is None:break
                        candidate=next(c for c in request['candidates'] if c['id']==selected)
                        if is_boundary(candidate):break
                        prefix.append(selected)
                    old_catalog={c['id']:c for c in row['request']['candidates']}
                    selected=[old_catalog[cid] for cid in (row.get('decision') or {}).get('candidate_ids',[])]
                    receipts=row.get('receipts',[])
                    monitor.record_actions(selected,receipts,goal_directions=current._progress_goal_directions)
                    if any(r.get('steps_used',0)>0 and r['skill']!='observe' for r in receipts):stationary.clear()
                    for receipt in receipts:
                        if receipt['skill']=='observe' and receipt['stop_reason']=='no_measured_scene_change':
                            stationary.add(old_catalog[receipt['candidate_id']]['parameters']['mode'])
                    print(json.dumps({'case':case['name'],'counts':dict(counts)}),flush=True)
                except Exception as exc:
                    errors.append({'case':case['name'],'line':line_index,'snapshot':reference,'error':repr(exc)})
                    print(json.dumps(errors[-1]),flush=True)
                if a.limit_requests and counts['requests']>=a.limit_requests:break
            if a.limit_requests and counts['requests']>=a.limit_requests:break
    report={'version':'M7-original220-schema6-rule-relabel/1','counts':dict(counts),
        'by_category':{k:dict(v) for k,v in categories.items()},'errors':errors,'excluded':excluded,
        'source_revision':a.source_revision,'source_files':files,'outcome_contract_sha256':outcome,
        'original_windows':{'path':str(a.windows),'sha256':sha(a.windows.read_bytes())},'registry':registry,
        'previous_usable_positions_user_reference':2414,'wall_s':time.perf_counter()-started,
        'process_cpu_s':time.process_time()-cpu_started,
        'parent_index':{'path':str(a.parent_index),'sha256':sha(a.parent_index.read_bytes())} if a.parent_index else None,
        'consumer_recheck':'C2 must retain splits and recompute new-request cross-split aliases before training',
        'vla_catalog_v2_active':False,'physics_steps':0,'rpc_calls':0,'gpu_used':False,
        'shard':a.shard,'shards':a.shards,'schema_sha256':files['rpent/skill_package/schema.json'],
        'contract_sha256':files['rpent/skill_package/contract.py'],
        'rows_sha256':sha((a.output/'positions.jsonl').read_bytes())}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    if errors:raise RuntimeError('M7 errors preserved; repair before releasing labels')


if __name__=='__main__':main()
