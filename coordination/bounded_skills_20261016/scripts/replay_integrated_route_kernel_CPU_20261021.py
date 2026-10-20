"""Compare source exact screening with its delivered kernel on pinned inputs."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.source=a.source.resolve(strict=True);sys.path.insert(0,str(a.source))
    import robots.libero.bounded_screen
    raw_manifest=a.manifest.read_bytes();manifest=json.loads(raw_manifest)
    calls=a.manifest.with_name('calls.jsonl');raw_calls=calls.read_bytes()
    assert hashlib.sha256(raw_calls).hexdigest()==manifest['calls_sha256']
    a.output.mkdir(exist_ok=False,parents=True);counts=Counter();differences=[];errors=[]
    times=Counter()
    with (a.output/'calls.jsonl').open('x',buffering=1) as out:
        for line in raw_calls.splitlines():
            source=json.loads(line)
            if source['kind']!='route':continue
            result={'input':source['input'],'input_sha256':source['input_sha256'],'context':source['context']}
            try:
                raw=gzip.decompress(Path(source['input']).read_bytes())
                assert hashlib.sha256(raw).hexdigest()==source['input_sha256']
                screen,args,kwargs=pickle.loads(raw)
                baseline,optimized=copy.deepcopy(screen),copy.deepcopy(screen)
                baseline.use_kernel=False;optimized.use_kernel=True
                results={}
                for name,instance in ([('baseline',baseline),('integrated',optimized)] if source['index']%2==0
                        else [('integrated',optimized),('baseline',baseline)]):
                    start=time.perf_counter();results[name]=instance(*args,**kwargs)
                    result[name+'_s']=time.perf_counter()-start;times[name]+=result[name+'_s']
                before,after=results['baseline'],results['integrated']
                equal=before==after
                result.update(full_result_equal=equal,baseline_passed=before['passed'],integrated_passed=after['passed'],
                    baseline_vs_recorded_equal=before==source['result'])
                counts['routes']+=1;counts['full_result_equal']+=equal
                counts['baseline_vs_recorded_differences']+=before!=source['result']
                counts['false_accepts']+=after['passed'] and not before['passed']
                if not equal:
                    differences.append({**result,'baseline':before,'integrated':after})
            except Exception as exc:
                result['error']=repr(exc);errors.append(result)
            out.write(json.dumps(result,allow_nan=False)+'\n')
    report={'source':str(a.source),'manifest':{'path':str(a.manifest),'sha256':hashlib.sha256(raw_manifest).hexdigest()},
        'counts':dict(counts),'timing_s':dict(times),'differences':differences,'errors':errors,
        'source_files':{str(p.relative_to(a.source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [a.source/'robots/libero/bounded_screen.py',a.source/'robots/libero/bounded_kernel_integration.py',
                *sorted((a.source/'robots/libero/bounded_kernels').glob('*.py'))]},
        'scope':'same captured incoming public route/IK/cache state, current source kernel OFF versus ON; historical cached verdicts retained separately',
        'physics_steps':0,'rpc_calls':0,'training':False}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    if errors or differences:raise RuntimeError('integrated kernel replay differences/errors retained')


if __name__=='__main__':main()
