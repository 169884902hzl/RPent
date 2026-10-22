"""Compare measured VLA completion to private labels on original-train data only."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022'
OUT=BASE/'option_ceiling_20261022/CPU_original_public_completion'

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--all', action='store_true', help='Retain correctly classified rows for public-evidence sensitivity analysis')
    args=parser.parse_args()
    out=[];counts=Counter();sources=[]
    for package in [BASE/'qualified90_9716b68c/CPU_closed90_r1',BASE/'layout_runtime_c7520ae1/CPU_C2_measured65_r1']:
        positions=package/'positions.jsonl';sources.append(ref(positions))
        for line in positions.open():
            position=json.loads(line)
            assert not position['PRO'] and not position['confirmation'] and position['source_split']=='train'
            worker=json.loads(Path(position['source']['path']).read_bytes())
            result=worker.get('result',worker)
            for trial in result['trials']:
                if trial['method']!='call_vla' or trial.get('truth_source')!='private_sustained_grasp_v3_post_branch_window':continue
                last=None
                for choice in Path(trial['choices']['path']).open():
                    record=json.loads(choice)
                    for detail in record.get('execution_details',[]):
                        execution=detail.get('execution',{})
                        if 'post_handoff_measurement' in execution:last=execution
                if last is None:
                    counts['no_public_completion_measurement']+=1;continue
                public=bool(last['post_handoff_measurement']['completed'])
                private=trial['success']
                key=('TP' if private else 'FP') if public else ('FN' if private else 'TN')
                counts[key]+=1
                if args.all or key in {'FP','FN'}:
                    measurement=last['post_handoff_measurement']
                    out.append({'case':worker['case']['name'],'category':worker['case']['category'],
                        'record_id':position['record_id'],'layout_domain':position.get('identity_domain','original'),
                        'trial_seed':trial['trial_seed'],'classification':key,
                        'public_completed':public,'private_success':private,
                        'reason':trial['reason'],'skill_stop_reason':last.get('skill_stop_reason'),
                        'post_hold':measurement.get('public_hold'),
                        'verification_motion':{k:v for k,v in last.get('verification_motion',{}).items()
                            if k in {'success','reason','stop_reason','steps_used','completed'}},
                        'handoff_controls':last.get('handoff',{}).get('steps_used'),
                        'final_vla_gripper':last['trace'][-1]['action'][-1] if last.get('trace') else None,
                        'choices':trial['choices'],'private_truth':trial['evidence']})
    args.output.mkdir(exist_ok=False)
    (args.output/('all_classifications.json' if args.all else 'misclassifications.json')).write_text(json.dumps(out,indent=2)+'\n')
    (args.output/'summary.json').write_text(json.dumps({'counts':dict(counts),'source_positions':sources,
        'FP_by_category':dict(Counter(r['category'] for r in out if r['classification']=='FP')),
        'FN_by_category':dict(Counter(r['category'] for r in out if r['classification']=='FN')),
        'thresholds_changed':False,'PRO':False,'D2':False,'confirmation':False,'training_executed':False},indent=2)+'\n')
    print(json.dumps({'counts':dict(counts),'out':str(args.output)}))

if __name__=='__main__':main()
