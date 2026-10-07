"""Summarize the immutable, explicitly located one-case job4463 smoke."""

import json
import subprocess
from pathlib import Path


REMOTE = r'''
from pathlib import Path
import hashlib,json
out=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave581_temporal_smoke_original_20261007/capture1')
plan_path=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave581_temporal_smoke_CPU_20261007/capture1.json')
log_path=Path('/public/home/sunyihan/rpent_libero_eval/results/slurm-4463.log')
ledger=out/'episodes.jsonl';plan=json.loads(plan_path.read_text());row=json.loads(ledger.read_text().splitlines()[0])
first=row['first_attempt'];records=first['verification_measurements']['microwave_temporal'];evidence=[]
for index,record in enumerate(records):
    frames=[]
    for frame in record['frames']:
        frames.append({k:frame.get(k) for k in ('source','frame_id','length_unit','source_step','source_cameras',
            'fusion_version','frame_moving_mask_overlap','measurement_counts','capture_version',
            'arm_withdrawn','occluded','proprioception','withdrawal','robot_mask_evidence','artifacts')})
    evidence.append({'index':index,'phase':record['phase'],'frames':frames})
refs=[]
for path,kind in [(ledger,'episodes_ledger'),(plan_path,'input_plan'),(log_path,'slurm_log')]:
    refs.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'kind':kind})
print(json.dumps({'job':4463,'slurm_state':'FAILED','slurm_exit_code':'1:0',
    'classification':'visited_original_bounded_startup_capture_smoke_not_skill_qualification',
    'raw_failure_text':'startup_error: no requested physical controls',
    'failure_root_cause':'Launcher looked for first_attempt.server_chunk_execution; actual controls are stored at row.server_chunk_execution.',
    'case':row['case']['name'],'episode':row['case']['episode'],'condition':plan['conditions'][row['case']['condition']],
    'status':row.get('status'),'raised_error':row.get('raised_error'),
    'infrastructure_failure':row.get('infrastructure_failure'),'eligible_physical_result':row.get('eligible_physical_result'),
    'wall_s':row.get('wall_s'),'server_chunk_execution':row.get('server_chunk_execution'),
    'first_attempt_executed_actions':first.get('executed_actions'),'first_attempt_physically_executed':first.get('physically_executed'),
    'first_attempt_receipt':first.get('receipt'),'first_private_before':first.get('private_before'),
    'first_private_after':first.get('private_after'),'temporal_records':evidence,
    'source_snapshot':plan['source_snapshot'],'launcher':plan['launcher'],'inputs':refs,
    'interpretation_limits':['Setup close did not establish closed state: private open predicate remained true before and after first open.',
        'Verified open and no_effect are compatible for an already-open door; this smoke does not prove first-attempt opening success.',
        'Private joint/predicate diagnostics are report labels only and must not enter runtime state or candidates.',
        'An eight-block capture smoke does not satisfy per-type skill confirmation thresholds.']},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    report=Path(__file__).parent/'report.json'
    if report.exists():
        raise SystemExit('Do not overwrite preserved evidence.')
    result=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                          input=REMOTE,text=True,capture_output=True,check=True)
    payload=json.loads(result.stdout)
    report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'job':payload['job'],'controls':payload['server_chunk_execution'],
                      'temporal_records':len(payload['temporal_records'])},ensure_ascii=False))
