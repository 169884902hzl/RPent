"""Compare v7 legacy invocations and the added measured preparation per state."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'


def reference(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2)


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;d=1+z*z/n
    c=(k/n+z*z/(2*n))/d
    h=z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/d
    return [max(0.,c-h),min(1.,c+h)]


def key(trial):
    return trial['method'],trial.get('vla_variant',{}).get('name'),trial['trial_seed']


def records(run,paths,outputs):
    result={}
    for panel_path,output in zip(paths,outputs):
        panel=json.loads(panel_path.read_bytes())
        for index,job in enumerate(panel['jobs']):
            pointer=output/f'closed_{index:03d}.json'
            closed=json.loads(pointer.read_bytes());raw=Path(closed['summary'])
            assert reference(raw)['sha256']==closed['sha256']
            row=json.loads(raw.read_bytes());name=job['case']['name']
            assert name==row['case']['name'] and name not in result
            assert row['restored_original_subtask_start']['same_captured_physics']
            result[name]={'job':job,'result':row,'raw':reference(raw)}
    return result


def counts(rows,field):
    known=[r[field] for r in rows if type(r[field]) is bool]
    k=sum(known)
    return {'n':len(rows),'known':len(known),'success':k,'unknown':len(rows)-len(known),
        'wilson95_over_trials':wilson(k,len(known))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--panel',choices=('155','N2'),required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.panel=='155':
        old=BASE/'regression155_f6987f0d'
        before=records(old,[old/f'preparation/shard{s}_physical_start.json' for s in range(2)],
            [old/f'shard{s}' for s in range(2)])
        after=records(a.run,[a.run/f'preparation/shard{s}.json' for s in range(2)],
            [a.run/f'formal155_shard{s}' for s in range(2)])
    else:
        old=BASE/'N2/after_fulltask'
        before=records(old,[old/'preparation/panel.json'],[old/'formal'])
        after=records(a.run,[a.run/'preparation/N2.json'],[a.run/'N2'])
    assert set(before)==set(after)
    paired,added,states=[],[],[]
    for name,new in after.items():
        previous=before[name];category=new['job']['case']['category']
        old_trials={key(t):t for t in previous['result']['trials']}
        expected=set(old_trials);seen=set()
        new_legacy=[];new_added=[]
        for t in new['result']['trials']:
            k=key(t)
            row={'case':name,'category':category,'method':k[0],'variant':k[1],'seed':k[2],
                'after_success':t['success'],'after_native_success':t.get('native_task_success'),
                'after_reason':t['reason'],'after_steps':t['sim_steps'],'after':new['raw']}
            if k[1]=='measured_anchor':
                added.append(row);new_added.append(t);continue
            prior=old_trials[k];seen.add(k);new_legacy.append(t)
            same_initial=prior['initial_physics_sha256']==t['initial_physics_sha256']
            row.update(before_success=prior['success'],before_native_success=prior.get('native_task_success'),
                before_reason=prior['reason'],before_steps=prior['sim_steps'],before=previous['raw'],
                same_complete_initial=same_initial,
                before_complete_initial_sha256=prior['initial_physics_sha256'],
                after_complete_initial_sha256=t['initial_physics_sha256'],
                same_candidate_id=prior.get('selected_candidate_id')==t.get('selected_candidate_id'),
                improved=prior['success'] is not True and t['success'] is True,
                regressed=prior['success'] is True and t['success'] is not True)
            paired.append(row)
        assert seen==expected and len(new_added)==3,(name,len(new_added),seen,expected)
        states.append({'case':name,'category':category,
            'old_native_successes':sum(t.get('native_task_success') is True for t in old_trials.values()),
            'new_legacy_native_successes':sum(t.get('native_task_success') is True for t in new_legacy),
            'measured_local_successes':sum(t['success'] is True for t in new_added),
            'measured_native_successes':sum(t.get('native_task_success') is True for t in new_added),
            'new_method_reasons':dict(Counter(t['reason'] for t in new_added)),
            'before':previous['raw'],'after':new['raw']})
    a.output.mkdir(parents=True,exist_ok=False)
    for filename,rows in [('paired_trials.jsonl',paired),('added_trials.jsonl',added),('states.jsonl',states)]:
        (a.output/filename).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    groups=defaultdict(list)
    for row in paired+added:groups[(row['category'],row['method'],row['variant'])].append(row)
    summary={'states':len(states),'paired_legacy_trials':len(paired),'added_trials':len(added),
        'source_commit':json.loads((a.run/'registration.json').read_bytes())['source_commit'],
        'before':counts(paired,'before_success'),'after_legacy':counts(paired,'after_success'),
        'improved':sum(r['improved'] for r in paired),'regressed':sum(r['regressed'] for r in paired),
        'complete_initial_mismatches':sum(not r['same_complete_initial'] for r in paired),
        'regressions':[r for r in paired if r['regressed']],
        'new_method':counts(added,'after_success'),'new_method_native':counts(added,'after_native_success'),
        'by_group':[{'category':k[0],'method':k[1],'variant':k[2],**counts(v,'after_success')}
            for k,v in sorted(groups.items(),key=lambda item:str(item[0]))],
        'new_method_reasons':dict(Counter(r['after_reason'] for r in added)),
        'rows':{n:reference(a.output/n) for n in ('paired_trials.jsonl','added_trials.jsonl','states.jsonl')},
        'training':False,'D2':False,'PRO':False,'confirmation':False,
        'scope':'subtask/registered native contracts reported separately; trial Wilson includes repeats, not independent layouts'}
    write(a.output/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ('states','paired_legacy_trials','added_trials','before','after_legacy','improved','regressed','complete_initial_mismatches','new_method')}))


if __name__=='__main__':main()
