"""Account for every priority1 query and combine only published train packets."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def checked(item):
    path=Path(item['path']);assert ref(path)==item,path
    return path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-incomplete',action='store_true')
    a=p.parse_args();base=a.run/'train_dagger_once_priority1';prep=base/'preparation'
    pending=[];outcomes=[];packets=[];all_jobs=[]
    for shard in range(62):
        manifest=prep/('pilot32_catalog_r3.json' if shard==0 else f'bulk_shard{shard:03d}.json')
        plan=json.loads(manifest.read_bytes());all_jobs.extend(plan['jobs'])
        results=base/('pilot32' if shard==0 else f'shard{shard:03d}')
        closed_refs=[]
        for i,job in enumerate(plan['jobs']):
            pointer=results/f'closed_{i:03d}.json'
            if not pointer.exists():pending.append({'source_order':job['source_order'],'query':job['query']});continue
            raw=json.loads(pointer.read_bytes());raw_path=checked(raw);report=json.loads(raw_path.read_bytes());closed_refs.append(raw)
            query=json.loads(checked(job['query']).read_bytes())
            assert query['split']=='train' and query['training_admission']
            status=report['status'];assert status in ('physical_result','unknown')
            outcomes.append({'source_order':job['source_order'],'old_query_id':query['query_id'],
                'old_record_id':query['record_id'],'new_query_id':report.get('new_query_id'),
                'category':job['case']['category'],'skill':query['candidate']['skill'],
                'original_prefix_length':len(query['prefix']),'status':status,
                'reason':report.get('reason'),'raw':raw})
        candidates=([base/'CPU_pilot32_closed/manifest.json'] if shard==0 else sorted((base/'exports').glob(f'shard{shard:03d}_job*/manifest.json')))
        found=[]
        if len(closed_refs)==len(plan['jobs']):
            for path in candidates:
                if not path.exists():continue
                value=json.loads(path.read_bytes())
                if {r['sha256'] for r in value['raw_sources']}=={r['sha256'] for r in closed_refs}:found.append((path,value))
        if found:
            assert len({v['data']['sha256'] for _,v in found})==1,'conflicting exports for one closed shard'
            packets.append(found[0])
    assert len(all_jobs)==1963 and len({j['source_order'] for j in all_jobs})==1963
    if not a.allow_incomplete:assert not pending and len(packets)==62,(len(pending),len(packets))
    a.output.mkdir(parents=True,exist_ok=False)
    data=a.output/'positions.jsonl';seen=set();by_category=Counter();by_skill=Counter();bound=0;unknown=0;replacements=[]
    with data.open('w') as stream:
        for packet,value in packets:
            assert value['source_split']=='train' and not any(value[k] for k in ('PRO','D2','confirmation'))
            for line in checked(value['data']).read_text().splitlines():
                row=json.loads(line);assert row['source_split']=='train' and not any(row[k] for k in ('PRO','D2','confirmation'))
                assert row['record_id'] not in seen;seen.add(row['record_id'])
                stream.write(line+'\n');by_category[row['case']['category']]+=1
                bound+=sum(len(b['trials']) for b in row['branches']);unknown+=len(row['unknown_trials'])
                for b in row['branches']:by_skill[b['method_family']]+=len(b['trials'])
            replacements.extend(json.loads(s) for s in checked(value['replacements']).read_text().splitlines())
    for name,rows in [('query_outcomes',outcomes),('pending',pending),('replacements',replacements)]:
        (a.output/f'{name}.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    summary={'version':'measured-subtask-choice/2','data':ref(data),'registered_queries':1963,
        'closed_queries':len(outcomes),'pending_queries':len(pending),'closed_packets':len(packets),
        'positions':len(seen),'bound_trials':bound,'unknown_trials':unknown,
        'unreached_or_unavailable_contexts':sum(r['status']=='unknown' for r in outcomes),
        'query_statuses':dict(Counter(r['status']+':'+str(r['reason'] or '') for r in outcomes)),
        'positions_by_category':dict(by_category),'known_trials_by_family':dict(by_skill),
        'queries_by_skill':dict(Counter(r['skill'] for r in outcomes)),
        'queries_by_prefix_length':dict(Counter(r['original_prefix_length'] for r in outcomes)),
        'unique_original_records':len({r['old_record_id'] for r in outcomes}),
        'packets':[ref(path) for path,_ in packets],'source_queries':plan['source_queries'],
        'replacements':ref(a.output/'replacements.jsonl'),'query_outcomes':ref(a.output/'query_outcomes.jsonl'),
        'training_executed':False,'training_admission':True,'source_split':'train',
        'PRO':False,'D2':False,'confirmation':False,'repeats_each':1,
        'one_trial_is_not_three_trial_acceptability_evidence':True,
        'scope':'new actually reached contexts; merge published packets once, not additional trials; no old-binding backfill',
        'incomplete':bool(pending) or len(packets)!=62}
    (a.output/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='packets'}))


if __name__=='__main__':main()
