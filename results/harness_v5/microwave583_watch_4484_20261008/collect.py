"""Summarize the fixed one-case capture8 smoke without directory scanning."""

import json
import subprocess
from pathlib import Path


REMOTE = r'''
from pathlib import Path
from collections import Counter
import hashlib,json
out=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave583_temporal_original_20261007/capture8')
ledger=out/'episodes.jsonl';raw=ledger.read_bytes();row=json.loads(raw.decode().splitlines()[0]);first=row['first_attempt']
records=first['verification_measurements']['microwave_temporal'];summaries=[]
for index,record in enumerate(records):
    measurement=record.get('measurement',{})
    summaries.append({'index':index,'phase':record['phase'],'baseline_attempt':record.get('baseline_attempt'),
        'chunks':record.get('chunks'),'measurement':measurement,
        'frames':[{k:f.get(k) for k in ('source','frame_id','length_unit','source_step','source_cameras',
            'fusion_version','timestamp_s','frame_moving_mask_overlap','capture_version','arm_withdrawn','occluded',
            'robot_mask_evidence','measurement_counts','frame','moving','withdrawal','proprioception','artifacts')}
            for f in record['frames']]})
frames=[f for r in summaries for f in r['frames']]
contract=out/'physical_startup_contract.json';log=Path('/public/home/sunyihan/rpent_libero_eval/results/slurm-4484.log')
refs=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ledger,contract,log)]
print(json.dumps({'format':'microwave583_smoke_watch/1','job':4484,'slurm_status':'COMPLETED','slurm_exit_code':'0:0',
    'case':row['case'],'source_snapshot_path':'/public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007',
    'status':row.get('status'),'infrastructure_failure':row.get('infrastructure_failure'),'raised_error':row.get('raised_error'),
    'server_chunk_execution':row['server_chunk_execution'],'first_physically_executed':first.get('physically_executed'),
    'first_executed_actions':first.get('executed_actions'),'first_receipt':first.get('receipt'),
    'private_before_label':first.get('private_before'),'private_after_label':first.get('private_after'),
    'physical_startup_contract':json.loads(contract.read_text()),'wall_s':row.get('wall_s'),
    'summary':{'temporal_records':len(records),'frames':len(frames),
        'plane_pairs_present':sum(isinstance(f.get('frame'),dict) and isinstance(f.get('moving'),dict) for f in frames),
        'camera_contribution_counts':dict(Counter(','.join(f.get('source_cameras') or []) for f in frames)),
        'arm_withdrawn_counts':dict(Counter(str(f.get('arm_withdrawn')) for f in frames)),
        'occlusion_counts':dict(Counter(str(f.get('occluded')) for f in frames)),
        'baseline_attempts':sum(r['phase']=='before' for r in records),
        'usable_baseline_attempts':sum(r['phase']=='before' and r['measurement'].get('status')=='measured' for r in records),
        'after_unmeasured_count':sum(r['phase']=='after' and r['measurement'].get('status')=='unmeasured' for r in records),
        'after_unmeasured_reason_counts':dict(Counter(r['measurement'].get('reason') for r in records if r['phase']=='after'))},
    'temporal_records':summaries,'inputs':refs,
    'limitations':['The setup did not close the microwave: before and after private open label was true at unchanged joint angle.',
        'This bounded eight-block original visited smoke is startup/measurement evidence, not first-attempt opening qualification.',
        'Active/fixed planes were detected, but a usable unobstructed two-frame baseline was never established; endpoint remains unknown.',
        'A fusion version string does not imply both cameras contributed to measured planes.',
        'Private joint state is a report label and was not a runtime sensor.']},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    report=Path(__file__).parent/'report.json'
    if report.exists():
        raise SystemExit('Do not overwrite preserved evidence.')
    run=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                       input=REMOTE,text=True,capture_output=True,check=True)
    result=json.loads(run.stdout)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary'],ensure_ascii=False))
