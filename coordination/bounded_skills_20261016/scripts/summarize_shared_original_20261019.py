"""Join the registered original220 ledger with its shared-launcher remainder."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def collect(preparation, results):
    plan=read(preparation/'batch_plan.json')
    batch=next(b for b in plan['batches'] if b['domain']=='original')
    manifest=Path(batch['manifest']['path'])
    assert hashlib.sha256(manifest.read_bytes()).hexdigest()==batch['manifest']['sha256']
    cases=read(manifest)['cases']
    records={}
    errors=[]
    def add(index,row,path):
        assert row['case']==cases[index] and row['arm']=='oracle_k4'
        assert row['status']=='physical_result' and row['pi05_calls']==0
        assert index not in records,('duplicate registered result',index)
        records[index]={'index':index,'record':str(path),'result':row}
    for entry in plan['already_completed']:
        path=Path(entry['record'])
        rows=[json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
        matched=[r for r in rows if r.get('status')=='physical_result'
            and r['case']==cases[entry['index']] and r['arm']=='oracle_k4']
        assert len(matched)==1
        add(entry['index'],matched[0],path)
    submission=read(preparation/'full_original_submission.json')
    for batch_index in submission['indices']:
        group=plan['batches'][batch_index]
        assert group['domain']=='original' and group['source_commit']==batch['source_commit']
        root=results/f'job{submission["job"]}_{batch_index}'/f'N{plan["selected_n"]}'
        for ordinal,index in enumerate(group['indices']):
            directory=root/f'{ordinal:03d}_{cases[index]["name"]}'
            path=directory/'worker_summary.json'
            if not path.exists():continue
            worker=read(path)
            assignment=read(directory/'assignment.json')
            assert assignment['case_index']==index and assignment['case']==cases[index]
            assert not assignment['startup'] and worker['source_commit']==batch['source_commit']
            if worker['exit_code']!=0:
                errors.append({'index':index,'worker_summary':str(path),'error':worker})
                continue
            add(index,worker['result'],path)
    return cases,records,errors,batch['source_commit']


def rate(values):
    n=len(values);s=sum(values)
    if not n:return {'n':0,'success':0,'rate':None,'wilson95':None}
    z=1.959963984540054;den=1+z*z/n
    centre=(s/n+z*z/(2*n))/den
    half=z*((s/n)*(1-s/n)/n+z*z/(4*n*n))**.5/den
    return {'n':n,'success':s,'rate':s/n,'wilson95':[centre-half,centre+half]}


def summarize(cases,records,errors,source):
    categories=defaultdict(list)
    for case in cases:categories[case['category']].append(case['name'])
    rows=[r['result'] for r in records.values()]
    groups=[]
    for category,names in sorted(categories.items()):
        selected=[r for r in rows if r['case']['category']==category]
        groups.append({'category':category,'registered_n':len(names),
            **rate([r['success'] for r in selected]),
            'failure_phases':dict(Counter(r['failure_phase'] for r in selected if not r['success']))})
    return {'source_commit':source,'registered_n':len(cases),**rate([r['success'] for r in rows]),
        'missing_indices':[i for i in range(len(cases)) if i not in records],
        'worker_errors':errors,'categories':groups,'records':[records[i] for i in sorted(records)],
        'scope':'registered original220 oracle_k4 only; no startup, throughput study, diagnostic reruns or D2 rows',
        'training':False,'pi05_disabled':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=summarize(*collect(args.preparation,args.results))
    with args.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps({k:result[k] for k in ('registered_n','n','success','rate','categories')}))


if __name__=='__main__':main()
