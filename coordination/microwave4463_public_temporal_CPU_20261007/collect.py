"""Read one explicit immutable public temporal ledger; no runtime mutation."""
import json
import subprocess
from pathlib import Path

REMOTE = r'''
from pathlib import Path
import json,hashlib
path=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave581_temporal_smoke_original_20261007/capture1/episodes.jsonl')
row=json.loads(path.read_text().splitlines()[0])
records=row['first_attempt']['verification_measurements']['microwave_temporal']
output=[]
for i,r in enumerate(records):
    frames=[]
    for f in r['frames']:
        frame={key:f.get(key) for key in ('source','frame_id','length_unit','source_step','source_cameras','timestamp_s','fusion_version','arm_withdrawn','occluded','frame_moving_mask_overlap','measurement_counts','frame','moving','interval_controls','interval_reason')}
        frame['views']={camera:{k:v for k,v in view.items() if k not in ('points','cloud','points_world','raw_points')} for camera,view in f.get('views',{}).items()}
        frame['robot_mask_evidence']={camera:{k:v for k,v in evidence.items() if k!='robot_mask_artifact'} for camera,evidence in f.get('robot_mask_evidence',{}).items()}
        frames.append(frame)
    output.append({'index':i,'phase':r['phase'],'chunks':r.get('chunks'),'measurement':r.get('measurement'),'frames':frames})
print(json.dumps({'job':4463,'source':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},'records':output}))
'''

if __name__ == '__main__':
    output=Path(__file__).parent/'public_records_v2.json'
    if output.exists():
        raise FileExistsError(output)
    result=subprocess.run(['timeout','25s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],input=REMOTE,text=True,capture_output=True,check=True)
    payload=json.loads(result.stdout)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'path':str(output.resolve()),'records':len(payload['records'])}))
