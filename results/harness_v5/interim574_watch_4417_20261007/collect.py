"""Read only the six completed, explicitly named job4417 shard ledgers."""

import json
import subprocess
from pathlib import Path


REMOTE = r'''
from pathlib import Path
from collections import Counter
import hashlib,json,math,statistics
base=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/expert/job4417')
inputs=[];cases=[]
for part in range(6):
    ledger=base/f'part{part}'/'probe'/'episodes.jsonl'
    raw=ledger.read_bytes()
    inputs.append({'path':str(ledger),'sha256':hashlib.sha256(raw).hexdigest(),'kind':'episodes_ledger'})
    for row in map(json.loads,raw.decode().splitlines()):
        result=row['result'];choices=Path(row['output_dir'])/'choices.jsonl'
        raw_choices=choices.read_bytes()
        inputs.append({'path':str(choices),'sha256':hashlib.sha256(raw_choices).hexdigest(),'kind':'choice_ledger'})
        decisions=[json.loads(x) for x in raw_choices.decode().splitlines()]
        attempts=Counter();verified=Counter();effects=Counter();fusion=Counter();cameras=Counter()
        chunks=steps=subtasks=with_changes=0;max_run=run=0;previous=None
        for d in decisions:
            receipt=d.get('receipt',{});tool=receipt.get('tool','unknown')
            attempts[tool]+=1
            if receipt.get('verification')=='verified':verified[tool]+=1
            effects[receipt.get('effect','missing')]+=1
            chunks+=max(int(receipt.get('chunks') or 0),int(receipt.get('primitive_result',{}).get('chunks_used') or 0))
            steps+=sum(int(e.get('steps_used',e.get('steps',0)) or 0) for e in d.get('motion_evidence',[]))
            subtasks+=tool=='vla_subtask';with_changes+=isinstance(receipt.get('measurement'),dict)
            chosen=d.get('selected');run=run+1 if chosen==previous else 1
            max_run=max(max_run,run);previous=chosen
            for key in ('perception_measurement_evidence','post_perception_measurement_evidence'):
                for e in d.get(key,{}).values():
                    fusion[e.get('fusion_version','missing')]+=1
                    for camera in e.get('source_cameras',[]):cameras[camera]+=1
        cases.append({'episode':row['episode'],'part':part,'official_success':bool(result.get('official_success')),
            'status':result.get('status'),'termination_category':result.get('termination_category'),
            'error':result.get('error'),'error_traceback':result.get('error_traceback'),
            'wall_s':result.get('wall_s'),'decisions_reported':result.get('decisions'),
            'choices_logged':len(decisions),'executed_vla_blocks_logged':chunks,
            'scripted_steps_logged':steps,'skill_attempts_logged':dict(attempts),
            'skill_verified_logged':dict(verified),'receipt_effects_logged':dict(effects),
            'receipts_with_measurement_change_dict':with_changes,'vla_subtask_attempts_logged':subtasks,
            'max_contiguous_identical_logged_action':max_run,'fusion_versions_logged':dict(fusion),
            'source_camera_observations_logged':dict(cameras),
            'source_hashes':result.get('source_hashes'),
            'source_hash_paths':result.get('source_hash_paths'),
            'ledger_path':str(ledger),'choices_path':str(choices)})

def wilson(n,k):
    if not n:return None
    z=1.959963984540054;ph=k/n;den=1+z*z/n
    center=(ph+z*z/(2*n))/den
    half=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
    return [center-half,center+half]
by_suite={}
for suite in sorted({x['episode']['suite'] for x in cases}):
    rows=[x for x in cases if x['episode']['suite']==suite];k=sum(x['official_success'] for x in rows)
    by_suite[suite]={'n':len(rows),'official_success':k,'wilson_95':wilson(len(rows),k),
        'errors':dict(Counter(x['error'] for x in rows if x['status']=='error'))}
errors=Counter(x['error'] for x in cases if x['status']=='error')
print(json.dumps({'job':4417,'classification':'partial_interim_development_only',
    'expected_full_cohort_n':200,'observed_completed_shard_rows':len(cases),
    'shards_read':[0,1,2,3,4,5],'held_shards_not_read':[6,7],
    'official_success':sum(x['official_success'] for x in cases),
    'wilson_95':wilson(len(cases),sum(x['official_success'] for x in cases)),
    'source_snapshot_path':'/public/home/sunyihan/rpent_libero_eval/source_v5_moka_startup_r4_20261007',
    'error_counts':dict(errors),'by_suite':by_suite,
    'median_wall_s':statistics.median(x['wall_s'] for x in cases),
    'executed_vla_blocks_logged':sum(x['executed_vla_blocks_logged'] for x in cases),
    'scripted_steps_logged':sum(x['scripted_steps_logged'] for x in cases),
    'max_contiguous_identical_logged_action':max(x['max_contiguous_identical_logged_action'] for x in cases),
    'episodes_max_contiguous_identical_logged_action_above5':sum(x['max_contiguous_identical_logged_action']>5 for x in cases),
    'interpretation_limits':['Interrupted error episodes may have physical execution omitted from the final failing JSON row.',
        'Counts are based only on persisted decisions; they are not the full 200-episode threshold.',
        'Fusion source evidence counts include before and after views and cached measurements.'],
    'inputs':inputs,'cases':cases},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    output=Path(__file__).parent/'report.json'
    if output.exists():
        raise SystemExit('Keep the existing report; choose another output for a new observation.')
    result=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                          input=REMOTE,text=True,capture_output=True,check=True)
    payload=json.loads(result.stdout)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:payload[k] for k in ('job','observed_completed_shard_rows','official_success',
          'by_suite','error_counts','median_wall_s','executed_vla_blocks_logged','scripted_steps_logged',
          'max_contiguous_identical_logged_action','episodes_max_contiguous_identical_logged_action_above5')},
          ensure_ascii=False))
