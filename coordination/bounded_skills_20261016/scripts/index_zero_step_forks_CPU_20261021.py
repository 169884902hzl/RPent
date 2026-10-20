"""Find closed census actions with an unchanged captured zero-control start."""
import argparse
from collections import Counter
import hashlib
import gzip
import json
from pathlib import Path
import re


def trials(value):
    if isinstance(value,dict):
        if all(k in value for k in ('choices','endpoint','initial_physics_sha256')):
            yield value
        else:
            for child in value.values():yield from trials(child)
    elif isinstance(value,list):
        for child in value:yield from trials(child)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--original-windows',type=Path,required=True)
    p.add_argument('--d2-manifest',type=Path,required=True)
    a=p.parse_args();cache={};counts=Counter();rows=[];seen=set();excluded=[]
    originals=json.loads(gzip.decompress(a.original_windows.read_bytes()))
    d2_plan=json.loads(a.d2_manifest.read_bytes())
    if len(originals['episodes'])!=220 or len(d2_plan['cases'])!=40:
        raise ValueError('expected the registered original220 and D2 forty')
    registrations={row['case']['name']:row['case'] for row in originals['episodes']}
    registrations.update({case['name']:case for case in d2_plan['cases']})
    for line in a.census.open():
        event=json.loads(line)
        if 'collision' not in event['primary_reason']:continue
        counts['census_collision_events']+=1
        name=event['case']
        original=bool(re.fullmatch(r'.+_libero_(spatial|object|goal|10|90)_t\d+_s\d+',name))
        d2=bool(re.fullmatch(r'libero_(spatial|object|goal|10)_(swap|task)_t[0-4]_s40',name))
        if not (original or d2):counts['outside_original_or_D2']+=1;continue
        identity=(event['file'],event['row_index'],event['candidate_id'])
        if identity in seen:continue
        seen.add(identity);matching=[];parent_payload=None;parent_path=None
        for parent in list(Path(event['file']).parents)[:5]:
            for filename in ('worker_summary.json','summary.json'):
                path=parent/filename
                if not path.is_file():continue
                if path not in cache:
                    raw=path.read_bytes();payload=json.loads(raw)
                    cache[path]=(payload,list(trials(payload)),hashlib.sha256(raw).hexdigest())
                payload,items,_=cache[path]
                matching=[item for item in items if item['choices'].get('path')==event['file']]
                if matching:parent_payload,parent_path=payload,path;break
            if matching:break
        if len(matching)!=1:
            counts['no_unique_closed_trial']+=1;continue
        trial=matching[0]
        if trial.get('sim_steps')!=0:
            counts['trial_has_controls']+=1;continue
        if trial['endpoint'].get('physics_sha256')!=trial['initial_physics_sha256']:
            counts['captured_start_endpoint_differ']+=1;continue
        choices=Path(event['file']).read_bytes()
        if hashlib.sha256(choices).hexdigest()!=trial['choices']['sha256']:
            excluded.append({'identity':identity,'reason':'choice_ledger_changed'});continue
        parsed=[json.loads(line) for line in choices.splitlines()]
        row=next((row for row in parsed if row.get('index')==event['row_index']),None)
        if row is None:counts['row_missing']+=1;continue
        candidate=next(c for c in row['request']['candidates'] if c['id']==event['candidate_id'])
        reference=trial['endpoint'];path=Path(reference['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
            excluded.append({'identity':identity,'reason':'endpoint_changed'});continue
        case=parent_payload.get('case')
        if not isinstance(case,dict):case=parent_payload.get('result',{}).get('case')
        if not isinstance(case,dict):case=registrations.get(name)
        if not isinstance(case,dict):counts['case_registration_missing']+=1;continue
        rows.append({'event':event,'case':case,'candidate':candidate,'endpoint':reference,
            'captured_initial_physics_sha256':trial['initial_physics_sha256'],
            'choices':trial['choices'],'source_summary':{'path':str(parent_path),'sha256':cache[parent_path][2]},
            'domain':'original' if original else 'D2_evaluation_only',
            'scope':'zero controls and exact equality of all historically captured state fields; restore then capture a new complete integration/RNG common start before branching',
            'training':False})
        counts['eligible/'+candidate['skill']]+=1
    a.output.mkdir(exist_ok=False,parents=True)
    data=a.output/'eligible.jsonl';data.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))
    report={'counts':dict(counts),'eligible':len(rows),'errors_or_changed_inputs':excluded,
        'census':{'path':str(a.census),'sha256':hashlib.sha256(a.census.read_bytes()).hexdigest()},
        'case_registrations':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in (a.original_windows,a.d2_manifest)],
        'rows_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'physics_steps':0,'rpc_calls':0,'training':False,'private_collision_truth_not_yet_measured':True}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    if excluded:raise RuntimeError('changed census inputs retained')


if __name__=='__main__':main()
