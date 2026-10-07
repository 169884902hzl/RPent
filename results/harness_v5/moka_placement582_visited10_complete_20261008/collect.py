"""Pin ten visited development states from startup4470 + formal4477."""

import hashlib
import json
import subprocess
from pathlib import Path


REMOTE = r'''
from pathlib import Path
from collections import Counter
import hashlib,json,math,statistics,subprocess
root=Path('/public/home/sunyihan/rpent_libero_eval')
manifest_path=root/'results/harness_v5/placement582_source_CPU_20261008/r2/moka_visited10.json'
manifest=json.loads(manifest_path.read_text());registered={case['name']:case for case in manifest['cases']}
inputs=[{'path':str(manifest_path),'sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'kind':'manifest'}]
cases=[]
ledgers=[root/'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/startup_preflight/4470/probe/episodes.jsonl']
ledgers += [root/f'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/smoke10/job4477/part{part}/probe/episodes.jsonl' for part in range(8)]
for ledger in ledgers:
    data=ledger.read_bytes();inputs.append({'path':str(ledger),'sha256':hashlib.sha256(data).hexdigest(),'kind':'episode_ledger'})
    for row in map(json.loads,data.decode().splitlines()):
        case=row['case'];name=case['name']
        if case['state_sha256']!=registered[name]['state_sha256']:raise ValueError('runtime state differs from manifest')
        choice_path=Path(row['output_dir'])/'choices.jsonl';raw=choice_path.read_bytes()
        inputs.append({'path':str(choice_path),'sha256':hashlib.sha256(raw).hexdigest(),'kind':'choices'})
        choices=[json.loads(line) for line in raw.decode().splitlines()]
        if len(choices)!=1:raise ValueError('owned startup expects one original transfer decision')
        choice=choices[0];receipt=choice['receipt'];evidence=choice['verification_measurements'];records=evidence.get('placement_endpoint_stop',[])
        admitted=[r for r in records if r.get('stop_admitted')]
        motion=choice.get('motion_evidence',[]);chunks=[e for e in motion if e.get('name')=='vla_act_chunk']
        contact_controls=sum(e.get('executed_action_count',0) for e in chunks)
        scope=row['server_chunk_execution']
        if contact_controls!=scope['executed_controls'] or scope['requested_controls']!=scope['executed_controls']:
            raise ValueError('contact trace and private server execution counter differ')
        neutral_hold_controls=sum(int(record.get('actual_hold_controls',0) or 0) for record in records)
        result=row['result'];truth=row['private_original_task_status_after']
        cases.append({'case_name':name,'episode':case['episode'],'state_sha256':case['state_sha256'],
            'previously_used_for_selection':case.get('previously_used_for_selection'),
            'excluded_from_training':case.get('excluded_from_training'),
            'job_id':'4470_0' if '/startup_preflight/' in str(ledger) else '4477_'+str(ledger.parts[-3].removeprefix('part')),
            'ledger':inputs[-2],'choices':inputs[-1],'result_status':result['status'],
            'error':result.get('error'),'case_had_infrastructure_failure':row.get('case_had_infrastructure_failure'),
            'official_success':result.get('official_success'),'native_terminated':result.get('native_terminated'),
            'private_before_done':row['private_original_task_status_before']['done'],'private_final_done':truth['done'],
            'server_chunk_execution':scope,'contact_trace_vla_chunks':len(chunks),
            'contact_trace_executed_controls':contact_controls,'neutral_stability_hold_controls_logged':neutral_hold_controls,
            'public_place_verified':row.get('public_placement_verdict'),
            'public_stop_admitted':bool(admitted),'stop_reason':receipt.get('stop'),
            'public_stop_records':len(records),'public_stop_status_counts':dict(Counter(r.get('status') for r in records)),
            'public_stop_reason_counts':dict(Counter(r.get('reason') for r in records)),
            'admitted_public_endpoint':admitted[-1] if admitted else None,
            'public_stop_true_private_final_false':bool(admitted) and truth['done'] is False,
            'ever_native_success_then_final_false':scope.get('raw_native_success_controls',0)>0 and truth['done'] is False,
            'wall_s':row.get('wall_s'),'source_hashes':result.get('source_hashes'),
            'source_hash_paths':result.get('source_hash_paths')})
cases.sort(key=lambda x:x['episode']['seed'])
if len(cases)!=10 or len({x['state_sha256'] for x in cases})!=10:raise ValueError('ten unique visited states required')
contract=root/'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/startup_preflight/4470/probe/contract.json'
inputs.append({'path':str(contract),'sha256':hashlib.sha256(contract.read_bytes()).hexdigest(),'kind':'startup_contract'})
z=1.959963984540054;n=len(cases);k=sum(x['private_final_done'] for x in cases);den=1+z*z/n
ph=k/n;center=(ph+z*z/(2*n))/den;half=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
sacct=subprocess.run(['sacct','-j','4470,4477','--format=JobID,State,ExitCode,Elapsed','-n','-P'],check=True,capture_output=True,text=True).stdout
print(json.dumps({'format':'moka_placement582_visited10/1','purpose':'visited development validation, not independent confirmation',
    'qualification_authorized':False,'training_allowed':False,'source_snapshot':manifest['source_snapshot'],
    'manifest_identity':inputs[0],'startup_contract':json.loads(contract.read_text()),'cases':cases,'inputs':inputs,'sacct':sacct,
    'summary':{'n':n,'private_final_done':k,'official_success':sum(x['official_success'] for x in cases),
        'public_place_verified_true':sum(x['public_place_verified'] is True for x in cases),
        'public_stop_admitted':sum(x['public_stop_admitted'] for x in cases),
        'public_stop_true_private_final_false':sum(x['public_stop_true_private_final_false'] for x in cases),
        'ever_success_then_final_false':sum(x['ever_native_success_then_final_false'] for x in cases),
        'contact_trace_chunks':sum(x['contact_trace_vla_chunks'] for x in cases),
        'contact_trace_controls':sum(x['contact_trace_executed_controls'] for x in cases),
        'neutral_stability_hold_controls_logged':sum(x['neutral_stability_hold_controls_logged'] for x in cases),
        'median_wall_s':statistics.median(x['wall_s'] for x in cases),'private_success_wilson_95':[center-half,center+half]},
    'limitations':['Ten previously selected states are development evidence only and cannot pass the independent 100-state gate.',
        'Public stop and private final done are reported separately; native latching never hides a false private endpoint.',
        'Contact counters exclude additional neutral stability controls; both are disclosed.',
        'The harness source label selects grasp, while the owned diagnostic adapter executes complete vla_subtask; receipt records the actual primitive.']},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    directory=Path(__file__).parent;report=directory/'report.json'
    if report.exists():
        raise SystemExit('Do not overwrite preserved evidence.')
    result=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                          input=REMOTE,text=True,capture_output=True,check=True)
    payload=json.loads(result.stdout)
    previous=directory.parent/'moka_visited10_complete_20261007/report.json'
    baseline=json.loads(previous.read_text());old={x['state_sha256']:x for x in baseline['cases']}
    pairs=[]
    for case in payload['cases']:
        before=old[case['state_sha256']]
        pairs.append({'episode':case['episode'],'state_sha256':case['state_sha256'],
            'old_private_final_done':before['private_final_done'],'new_private_final_done':case['private_final_done'],
            'old_public_place_verified':before['public_place_verified'],'new_public_place_verified':case['public_place_verified'],
            'old_contact_controls':before['server_chunk_execution']['executed_controls'],
            'new_contact_controls':case['contact_trace_executed_controls']})
    payload['previous_mixed_source_development_reference']={'path':str(previous.resolve()),
        'sha256':hashlib.sha256(previous.read_bytes()).hexdigest(),'commit':'1da95b8'}
    payload['paired_development']={'old_success':sum(x['old_private_final_done'] for x in pairs),
        'new_success':sum(x['new_private_final_done'] for x in pairs),
        'improved':sum(not x['old_private_final_done'] and x['new_private_final_done'] for x in pairs),
        'regressed':sum(x['old_private_final_done'] and not x['new_private_final_done'] for x in pairs),'pairs':pairs,
        'comparison_limit':'Repeated visited states with multiple code changes; not isolated causal evidence or confirmation.'}
    report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'summary':payload['summary'],'paired':{k:v for k,v in payload['paired_development'].items() if k!='pairs'}},ensure_ascii=False))
