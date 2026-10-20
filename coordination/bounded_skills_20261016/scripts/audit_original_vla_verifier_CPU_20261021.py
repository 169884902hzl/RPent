"""Compare retained original-only public VLA receipts with private outcomes."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path


def checked(ref):
    raw=Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('retained source changed: '+ref['path'])
    return raw


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    mid=(p+z*z/(2*n))/d;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [mid-half,mid+half]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(exist_ok=False,parents=True)
    rows=[];errors=[];groups=defaultdict(Counter);cache={};outside=Counter();unscored=[]
    for line in a.ledger.open():
        source=json.loads(line)
        if source.get('method')!='call_vla':
            outside[source.get('method','no_trial_result')]+=1
            if 'method' not in source:unscored.append(source)
            continue
        if any(s in source['case'] for s in ('_swap_','_task_')) or source['confirmation']:
            raise ValueError('PRO/D2/confirmation is forbidden for verifier calibration')
        try:
            path=source['source_path']
            if path not in cache:
                cache[path]=json.loads(checked({'path':path,'sha256':source['source_sha256']}))['result']
            trial=cache[path]['trials'][source['trial_index']]
            if trial['method']!='call_vla' or trial['trial_seed']!=source['seed']:
                raise ValueError('trial identity mismatch')
            choices=checked(trial['choices']);checked(trial['evidence'])
            receipts=[r for raw in choices.splitlines() for r in json.loads(raw)['receipts'] if r['skill']=='call_vla']
            public=receipts[-1]['outcome'] if receipts else 'missing_receipt'
            truth=trial['success'];mode=trial['subtask']['mode']
            if type(truth) is not bool or public not in {'success','failure','rejected'}:
                classification='unknown'
            else:
                classification=('TP' if truth else 'FP') if public=='success' else ('FN' if truth else 'TN')
            row={'case':source['case'],'mode':mode,'seed':source['seed'],
                'source_revision':source['source_revision'],'source':{'path':path,'sha256':source['source_sha256']},
                'choices':trial['choices'],'truth':trial['evidence'],'truth_source':trial['truth_source'],
                'private_subtask_success':truth,'public_final_outcome':public,
                'public_stop_reasons':[r['stop_reason'] for r in receipts],'classification':classification,
                'schema_version':source['schema_version'],'training':False,'pro':False,'confirmation':False}
            rows.append(row);groups['all'][classification]+=1;groups[mode][classification]+=1
        except Exception as exc:errors.append({'source':source['source_path'],'trial_index':source['trial_index'],'error':repr(exc)})
    summary={}
    for mode,c in groups.items():
        n=sum(c[x] for x in ('TP','FP','FN','TN'));k=c['TP']+c['TN']
        summary[mode]={**dict(c),'known':n,'agreement':k/n if n else None,'wilson95':wilson(k,n)}
    output=a.output/'rows.jsonl';output.write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    report={'source_ledger':{'path':str(a.ledger),'sha256':hashlib.sha256(a.ledger.read_bytes()).hexdigest()},
        'by_mode':summary,'trials':len(rows),'errors':errors,'outside_vla_cohort':dict(outside),
        'unscored_source_rows':unscored,'rows_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'scope':'retained original-development schema4 receipts versus final private subtask predicate; no rescoring of confirmations, no schema6 label migration',
        'thresholds_changed':False,'physics_steps':0,'rpc_calls':0,'training':False}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    if errors:raise RuntimeError('verifier audit errors retained')


if __name__=='__main__':main()
