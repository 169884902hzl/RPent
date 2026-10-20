"""Replay real public IK inputs with only result-cache disabled, timing cold solves."""
import argparse
import collections
import gzip
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    sys.path.insert(0,str(args.source))
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'inputs').mkdir()
    groups=collections.defaultdict(list)
    for path in sorted(args.corpus.glob('original_shard*/calls.jsonl')):
        for line in path.open():
            row=json.loads(line)
            if row['kind']=='ik':groups[row['context']['category']].append(row)
    count=0
    with (args.output/'calls.jsonl').open('x',buffering=1) as stream:
        for offset in range(max(map(len,groups.values()))):
            for category,rows in sorted(groups.items()):
                if offset>=len(rows) or count>=args.limit:continue
                old=rows[offset]
                raw=gzip.decompress(Path(old['input']).read_bytes())
                if hashlib.sha256(raw).hexdigest()!=old['input_sha256']:raise ValueError('changed input')
                instance,positional,kwargs=pickle.loads(raw)
                instance.cache={}
                raw=pickle.dumps((instance,positional,kwargs),protocol=5)
                digest=hashlib.sha256(raw).hexdigest()
                target=args.output/'inputs'/(digest+'.pkl.gz')
                if not target.exists():target.write_bytes(gzip.compress(raw,compresslevel=1,mtime=0))
                begin=time.perf_counter();result=instance.check(*positional,**kwargs);elapsed=time.perf_counter()-begin
                count+=1
                stream.write(json.dumps(dict(kind='ik',index=count,context={**old['context'],
                    'cold_result_cache_disabled':True,'original_input_sha256':old['input_sha256']},
                    input=str(target),input_sha256=digest,wall_s=elapsed,result=result,
                    historical_cached_solution_found=old['result']['solution_found']))+'\n')
            if count>=args.limit:break
            if count%50==0:print(count,flush=True)
    manifest=dict(version='public-screen-call-corpus/1',counts={'ik':count},
        source=str(args.source),source_commit='333d12c6e5f356f2cca9ae12f37e142a530e2f89',
        calls_sha256=hashlib.sha256((args.output/'calls.jsonl').read_bytes()).hexdigest(),
        scope='same recorded public measurements, targets and incoming joint states; only IK result cache emptied',
        physics_steps=0,rpc_calls=0,training=False,pro=False,confirmation=False)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)


if __name__=='__main__':main()
