"""Read registered original-only probes; truth references remain diagnostics."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from robots.libero.v5_runtime import category


def summarize(root, plan):
    ledger=root/'episodes.jsonl'
    rows=list(map(json.loads,ledger.read_text().splitlines()))
    names=defaultdict(Counter)
    errors=defaultdict(list)
    counts=Counter()
    walls=[]
    for entry in rows:
        r=entry['result'];walls.append(r['wall_s']);counts[r.get('termination_category','unknown')]+=1
        path=Path(entry['output_dir'])/'choices.jsonl'
        for row in map(json.loads,path.read_text().splitlines()) if path.exists() else []:
            reference=(row.get('localization_diagnostic') or {}).get('reference',{})
            measured={e['id']:e for e in row['measurements']}
            for e in measured.values():
                if not e['visible'] or e.get('part_of') or e['name'].startswith('area '):continue
                matches=[v for k,v in reference.items() if category(k)==e['name']]
                peers=[x for x in measured.values() if x['visible'] and x['name']==e['name']]
                if len(matches)==len(peers)==1:
                    distance=math.dist(e['xyz'][:2],matches[0]['xyz'][:2])*100
                    errors[e['name']].append(distance)
            receipt=row['receipt']
            if receipt.get('tool') in ('grasp','regrasp_restage'):
                name=measured.get(receipt.get('object'),{}).get('name','unknown')
                names[name]['attempts']+=1
                names[name]['visual_grasp_verified']+=receipt.get('grasp_verified') is True
                names[name]['execution_error']+=bool(receipt.get('error'))
    attempted=sum(v['attempts'] for v in names.values())
    return {'planned':len(plan['episodes']),'completed':len(rows),'complete':len(rows)==len(plan['episodes']),
        'actual_grasp_attempts':attempted,'at_least_50_grasps':attempted>=50,
        'grasp_by_category':{k:dict(v) for k,v in names.items()},
        'xy_error_cm_to_body_origin':{k:{'n':len(v),'median':statistics.median(v),'mean':statistics.mean(v)} for k,v in errors.items()},
        'wall_median_s':statistics.median(walls) if walls else None,'termination_categories':dict(counts),
        'scope':'single original-task skill probes; visual grasp success is separate from official task completion; body-origin references are private diagnostic labels'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();index=json.loads(a.index.read_text());report={'conditions':{}}
    for item in index['plans']:
        path=Path(item['path']);raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('plan changed')
        report['conditions'][item['condition']]=summarize(a.root/item['condition'],json.loads(raw))
    report['index_sha256']=hashlib.sha256(a.index.read_bytes()).hexdigest()
    a.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
