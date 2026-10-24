"""Replay actual requests/receipts; no policy, simulation or private goal calls."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, sys

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.source))
from rpent.skill_package.contract import FailureMemory, identity

args.output.mkdir(parents=True,exist_ok=True)
counts=Counter();reasons=Counter();rows=[];case_rows=[]
for file in sorted(args.input.glob('case*/choices.jsonl')):
    counts['cases']+=1
    previous=None;streak=0;local=Counter();segment=FailureMemory()
    for line in file.open():
        x=json.loads(line);request=x['request'];candidates={c['id']:c for c in request['candidates']}
        counts['requests']+=1
        # Existing source counts provide exact, actual-history evidence; do
        # not invent object-motion labels from shifted segmentation centres.
        frozen=FailureMemory()
        for c in candidates.values():
            frozen.counts[identity(c)]=c.get('recent_failures',0)
            frozen.last[identity(c)]=c.get('last_failure')
        after_ids={c['id'] for c in frozen.apply(list(candidates.values()))}
        counts['source_count_candidates_blocked']+=len(candidates)-len(after_ids)
        for receipt in x['receipts']:
            c=candidates[receipt['candidate_id']];key=identity(c)
            blocked_by_source_count=c['id'] not in after_ids
            blocked_same_world=not bool(segment.apply([c]))
            if previous is not None and key==previous['key']:
                counts['consecutive_same_skill_parameters']+=1
                streak+=1
                if previous['outcome'] in {'failure','no_effect','rejected','unmeasured'}:
                    counts['consecutive_after_failure']+=1
                    if c['skill'] in {'move_to','call_vla'}:
                        counts['move_or_vla_consecutive_after_failure']+=1
                if previous['phase']=='planning_unreachable':
                    counts['consecutive_after_planning_unreachable']+=1
                if previous['steps']==0:
                    counts['consecutive_after_zero_control']+=1
                if previous['id']!=c['id']:
                    counts['same_parameters_different_candidate_id']+=1
            else:
                streak=1
            counts['longest_same_parameter_run']=max(counts['longest_same_parameter_run'],streak)
            if previous is not None and previous['steps']==0:
                anchors={a['id']:a['xyz_m'] for a in request['anchors']}
                old=previous['anchors']
                if set(anchors)-set(old):counts['new_detection_after_zero_control']+=1
                if any(sum((a-b)**2 for a,b in zip(anchors[k],old[k]))>.01**2 for k in set(anchors)&set(old)):
                    counts['centre_shift_over_1cm_after_zero_control']+=1
            if blocked_by_source_count:
                counts['selected_blocked_by_actual_failure_count']+=1;local['actual_count_blocks']+=1
                reasons[receipt['stop_reason']]+=1
            if blocked_same_world:
                counts['selected_blocked_in_unchanged_physics_segment']+=1;local['same_world_blocks']+=1
            rows.append({'case':file.parent.name,'index':x['index'],'candidate_id':c['id'],
                'skill':c['skill'],'parameters':c['parameters'],'recent_failures':c.get('recent_failures'),
                'blocked_by_actual_source_count':blocked_by_source_count,
                'blocked_after_two_failures_in_no_control_segment':blocked_same_world,
                'outcome':receipt['outcome'],'reason':receipt['stop_reason'],'steps':receipt['steps_used']})
            if receipt['steps_used']>0:
                # The new-world counterfactual requires saved-depth verification.
                # Reset here to obtain a conservative count for exact no-step
                # segments only, not a pretend whole-episode replay result.
                segment=FailureMemory()
            segment.record(c,receipt['outcome'],receipt['stop_reason'])
            previous={'key':key,'id':c['id'],'outcome':receipt['outcome'],'phase':receipt['phase'],
                'steps':receipt['steps_used'],'anchors':{a['id']:a['xyz_m'] for a in request['anchors']}}
    case_rows.append({'case':file.parent.name,**dict(local),'input_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
report={'counts':dict(counts),'blocked_receipt_reasons':dict(reasons),
    'counterfactual_scope':'public source counts and exact zero-control segments; no alternative actions executed; no task-success estimate',
    'root_causes':{'candidate_ID_based':False,'aggressive_bypasses_failure_limit':True,
        'zero_control_failure_recorded':True,'centre_only_scene_reset_can_clear_failures':True},
    'source':str(args.source),'contract_sha256':hashlib.sha256((args.source/'rpent/skill_package/contract.py').read_bytes()).hexdigest(),
    'simulation_steps':0,'policy_calls':0,'private_truth_calls':0}
(args.output/'rows.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
(args.output/'cases.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in case_rows))
(args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
