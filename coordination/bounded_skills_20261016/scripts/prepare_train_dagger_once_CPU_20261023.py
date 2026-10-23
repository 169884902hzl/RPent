"""Pin train-only queries in source order; current user asks one physical repeat."""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
RUN=ROOT/'results/bounded_skills/next_b_pi_first_20261023'
Q=Path('/public/home/sunyihan/rd_instruction_20260923/c2_pi_default_20261023_0150/DAgger_priority/C3_train_DAgger_queries_priority1.jsonl')
OUT=RUN/'train_dagger_once_priority1/preparation'
OUT.mkdir(parents=True,exist_ok=False)

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

assert ref(Q)['sha256']=='ae79127421113b03369e4f63fe130d4e27e6d91f1d746b89c1c14cdf730a00af'
cohort_path=ROOT/'results/bounded_skills/feasibility_20261017/preparation/original20_manifest_support_roundrobin_20261018.json'
cohort=json.loads(cohort_path.read_text());cases={c['name']:c for c in cohort['cases']}
calibration=ref(ROOT/'results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json')
source=ROOT/'source_pi_first_origin_f6ce1d46_20261023'
rows=[json.loads(s) for s in Q.read_text().splitlines()]
selected=[(i,q) for i,q in enumerate(rows) if q['collection_required_under_current_contract']]
assert len(selected)==1963
jobs=[];skipped=[]
for index,q in selected:
    assert q['domain']=='libero' and q['split']=='train' and q['training_admission'] and q['future_training_admission_under_current_contract']
    assert q['snapshot_verified'] and q['current_legality_audit']['selected_candidate_currently_legal']
    if q['outcome_contract'] is None:
        case=copy.deepcopy(cases[q['episode_id']])
        assert q['private_prefix_annotation_state'] is not None
    else:
        raw=json.loads(Path(q['source_link']['path']).read_text())
        case=copy.deepcopy(raw['case'])
    case['origin_case_purpose']=case.get('purpose')
    case['purpose']='original_train_dagger_physical_candidate_measurement'
    case['grasp_measurement_calibration']=calibration
    assert case['episode']['suite'] in {'libero_spatial','libero_object','libero_goal','libero_10','libero_90'}
    assert q['original_task_key']==case['episode']['suite']+'/t'+str(case['episode']['task'])
    assert q['original_init']==case['episode']['seed']
    path=OUT/f'query_{index:04d}.json';path.write_text(json.dumps(q,ensure_ascii=False))
    origin=None
    root=Path(q['private_physical_snapshot']['path'])
    if root.parent.name=='private_decision_snapshots' and (root.parent/'000.pkl').is_file():origin=ref(root.parent/'000.pkl')
    jobs.append({'query':ref(path),'source_order':index,'case':case,'execution_source':str(source),
        'episode_origin':origin,'repeats':1,'seed':62000000+index*1000})
for i,q in enumerate(rows):
    if not q['collection_required_under_current_contract']:
        skipped.append({'source_order':i,'query_id':q['query_id'],'reason':'superseded_human_unavailable_ask_help; not a physical failure'})
header={'version':'original-train-dagger-once/1','source_queries':ref(Q),'source_cohort':ref(cohort_path),
    'permanent_exclusions':cohort['permanent_exclusions'],
    'frozen_parent_index':ref(ROOT/'M7_parent_index_20261021.json'),
    'libero_config':ref(ROOT/'runtime_config_original_20261023/config.yaml'),
    'sam_entry':ref(ROOT/'sam3_feature_cache_startup_20261020.py'),
    'measurement_producer':ref(ROOT/'evaluate_bounded_training_candidate_20261023.py'),
    'training':False,'training_split_collection':True,'PRO':False,'D2':False,'confirmation':False,
    'valid_labels_may_enter_next_training_only':True,'requested_repeats':1,
    'ordering':'C2 priority1 file order: model top1 per state, opening first steps, frequency; no outcome-based prioritization',
    'binding_policy':'physically execute ordered prefix; unreachable=>unknown; new actual request/context gets new record and explicit replacement mapping; no old-context backfill'}
for shard in range((len(jobs)+31)//32):
    plan={**header,'jobs':jobs[shard*32:(shard+1)*32]}
    (OUT/f'shard{shard:03d}.json').write_text(json.dumps(plan,indent=2))
summary={'retained':len(rows),'collectable':len(jobs),'superseded':len(skipped),
    'repeats_each':1,'shards':(len(jobs)+31)//32,
    'by_skill':dict(Counter(q['candidate']['skill'] for _,q in selected)),
    'prefix_lengths':dict(Counter(len(q['prefix']) for _,q in selected)),
    'existing_outcome_contracts':sum(q['outcome_contract'] is not None for _,q in selected),
    'legacy_contract_registration_before_candidate':'source-register generic next pending subgoal after actual prefix, prior to candidate execution; provided contracts remain semantically unchanged',
    'sources':header,'GPU_jobs_submitted':False}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2));(OUT/'superseded.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in skipped))
print(json.dumps({k:v for k,v in summary.items() if k!='sources'}))
