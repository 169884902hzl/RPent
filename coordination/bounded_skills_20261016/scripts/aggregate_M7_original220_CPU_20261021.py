"""Close M7 shards without changing source splits or inventing VLA labels."""
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shards',type=Path,nargs='+',required=True)
    p.add_argument('--parent-index',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();parent=json.loads(a.parent_index.read_bytes())
    manifests=[json.loads((path/'manifest.json').read_bytes()) for path in a.shards]
    first=manifests[0]
    if sorted(m['shard'] for m in manifests)!=list(range(first['shards'])):
        raise ValueError('every CPU shard must be closed exactly once')
    for m in manifests:
        for key in ('source_revision','source_files','original_windows','registry','parent_index'):
            if m[key]!=first[key]:raise ValueError('mixed M7 inputs: '+key)
        if m['errors']:raise ValueError('M7 errors must be repaired before release')
    if first['parent_index']['sha256']!=digest(a.parent_index):
        raise ValueError('parent split/comparison inventory changed')
    a.output.mkdir(parents=True,exist_ok=False)
    counts=Counter();categories=defaultdict(Counter);splits=defaultdict(Counter)
    seen=set();requests=set();accepted_parent=set();excluded=[]
    rows=a.output/'positions.jsonl.gz'
    with rows.open('xb') as raw_out,gzip.GzipFile(fileobj=raw_out,mode='wb',mtime=0,compresslevel=1) as output:
        for path,m in zip(a.shards,manifests):
            source=path/'positions.jsonl'
            if digest(source)!=m['rows_sha256']:raise ValueError('M7 rows changed')
            excluded.extend(m['excluded'])
            for raw in source.open('rb'):
                row=json.loads(raw)
                if row['record_id'] in seen:raise ValueError('duplicate M7 position')
                seen.add(row['record_id']);requests.add(row['parent_record_id'])
                if row['pro'] or row['confirmation']:raise ValueError('forbidden training domain')
                binding=row['binding'];prefix=row['prefix'];request=row['public_request']
                canonical=json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
                if hashlib.sha256(canonical).hexdigest()!=binding['request_sha256']:
                    raise ValueError('request binding mismatch')
                if prefix!=binding['prefix'] or row['snapshot']['sha256']!=binding['snapshot_sha256']:
                    raise ValueError('prefix/snapshot binding mismatch')
                if not set(row['acceptable'])<=set(row['legal']):raise ValueError('illegal positive label')
                if set(row['acceptable'])&set(row['unknown_candidate_ids']):
                    raise ValueError('unknown candidate became a positive label')
                if row['measured_success'] or row['measured_failure']:
                    raise ValueError('CPU rules cannot assert physical branch results')
                frozen=parent['parents'][row['parent_record_id']]
                if row['source_parent']!=frozen:raise ValueError('source split or exclusion changed')
                effective=bool(row['acceptable']) and len(row['acceptable'])<len(row['legal']) and len(request['candidates'])<=94
                eligible=effective and frozen['status']=='ok'
                for c in (counts,categories[row['category']],splits[frozen['split']]):
                    c['positions']+=1;c['effective_positions']+=effective
                    c['source_eligible_effective_positions']+=eligible
                if eligible:accepted_parent.add(row['parent_record_id'])
                output.write(raw)
    expected=Counter()
    for m in manifests:expected.update(m['counts'])
    for key in ('positions','effective_positions','source_eligible_effective_positions'):
        if counts[key]!=expected[key]:raise ValueError('aggregate count mismatch: '+key)
    missing=set(parent['parents'])-requests
    excluded_cases={r['case'] for r in excluded}
    unexplained=[key for key in missing if key.split('/')[1] not in excluded_cases]
    if unexplained:raise ValueError('original requests not closed: '+str(unexplained[:10]))
    comparison={category:{'before_usable':parent['by_category'].get(category,0),**dict(categories[category]),
        'source_eligible_delta':categories[category]['source_eligible_effective_positions']-parent['by_category'].get(category,0)}
        for category in sorted(set(parent['by_category'])|set(categories))}
    report=dict(version='M7-original220-schema6-rule-relabel/1',source_revision=first['source_revision'],
        source_files=first['source_files'],counts=dict(counts),requests=len(requests),
        source_eligible_requests=len(accepted_parent),by_category=comparison,
        by_split={key:dict(value) for key,value in splits.items()},
        before_usable_positions=2414,source_eligible_delta=counts['source_eligible_effective_positions']-2414,
        rows={'path':str(rows),'sha256':digest(rows)},excluded=excluded,errors=[],
        shard_manifests=[{'path':str(path/'manifest.json'),'sha256':digest(path/'manifest.json')} for path in a.shards],
        process_cpu_s=sum(m['process_cpu_s'] for m in manifests),
        worker_wall_s=sum(m['wall_s'] for m in manifests),physics_steps=0,rpc_calls=0,gpu_used=False,
        caveat='Conditional rule labels, not physical success. Source exclusions/splits retained; C2 must recompute cross-split aliases on new requests before training.')
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
