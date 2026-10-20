"""Register schema6 original forks, drawer pairs, fixed N1 and D2 recovery arms."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    with path.open('x') as stream:json.dump(value,stream,indent=2)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--commit',required=True)
    args=p.parse_args();root=args.root.resolve(strict=True);source=args.source.resolve(strict=True)
    directory=root/'results/bounded_skills/schema6_20261020/preparation'
    directory.mkdir(parents=True,exist_ok=True)
    progress=root/'results/bounded_skills/schema6_20261020/original220_progress_r2.json'
    registered=json.loads(progress.read_bytes());assert registered['selected_N']==31
    d2_parent=root/'results/bounded_skills/D2_public_binding_hybrid_20261020/3968bdb4/preparation/manifest.json'
    d2=json.loads(d2_parent.read_bytes());calibration=d2['cases'][0]['grasp_measurement_calibration']
    old=json.loads((root/'results/bounded_skills/D2_cached_binding_hybrid_20261020/3968bdb4/preparation/batch_plan.json').read_bytes())
    sam=old['sam3_entry']
    base={'schema_version':'bounded-skills/6','source':str(source),'source_commit':args.commit,
        'sam_entry':sam,'training':False,'confirmation':False,
        'progress_registration':ref(progress),'runtime_budget':{'sim_steps':10000,'decisions':160},
        'resume_unit':'completed registered case; interrupted records preserved'}
    jobs=[]
    for position in registered['move_fork_registration']:
        case=copy.deepcopy(position['case']);case['grasp_measurement_calibration']=calibration
        jobs.append({'kind':'move','position':position,'case':case})
    assert len(jobs)>=100
    write(directory/'move100.json',{**base,'jobs':jobs})
    # Original220 is twenty original states per registered category. No
    # post-result selection, new states, confirmation states or PRO inputs.
    original=root/'coordination/bounded_skills_20261016/reports/original220_shared_closed_20261020.json'
    rows=json.loads(original.read_bytes())['records']
    jobs=[]
    for row in rows:
        case=row['result']['case']
        if case['category'] not in ('drawer_open','drawer_close'):continue
        case=copy.deepcopy(case);case['grasp_measurement_calibration']=calibration
        jobs.append({'kind':'drawer','case':case,'historical_result':row['record']})
    if len(jobs)!=40:
        raise ValueError(f'expected20 original drawer states per direction, got{len(jobs)}')
    write(directory/'drawer40.json',{**base,'jobs':jobs})
    n1_parent=root/'results/bounded_skills/latency_fixed32_20261020/preparation/manifest_speed_91307c12.json'
    n1=copy.deepcopy(json.loads(n1_parent.read_bytes()))
    n1.update(baseline_source=str(source),baseline_commit=args.commit,baseline_schema='bounded-skills/6',
        schema6_source=True,comparison_changes=['merged_move','guarded_move','incremental_perception',
            'original220_stagnation31','cheap_prefix_reuse','batched_public_geometry'])
    n1['scene_options']={'rgbd_mask_tracking_v1':True}
    n1['parents'].append(ref(n1_parent))
    write(directory/'N1_fixed32.json',n1)
    for budget in (0,1,2):
        jobs=[{'kind':'d2','case':case,'manifest':ref(d2_parent),'recovery_budget':budget}
            for case in d2['cases']]
        write(directory/f'D2_recovery{budget}.json',{**base,'jobs':jobs,
            'evaluation_only':True,'recovery_budget':budget,'private_rules_unchanged':True})
    # Only the unfinished case of cancelled10688, keeping its old source,
    # settings and existing completed denominator separate from schema6.
    batch=copy.deepcopy(old['batches'][2]);batch['indices']=[14]
    assert d2['cases'][14]['name']=='libero_spatial_task_t4_s40'
    write(directory/'old3968_unfinished_plan.json',{**old,'batches':[batch]})
    print(json.dumps({'preparation':str(directory),'move_pairs':100,'drawer_pairs':40,
        'N1':32,'D2':{'0':40,'1':40,'2':40},'old_unfinished':1}))


if __name__=='__main__':main()
