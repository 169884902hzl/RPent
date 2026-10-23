"""Three exact-binding repeats of the explicitly registered train defaults."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def reference(path):
    import hashlib
    return {'path':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def checked(value):
    path=Path(value['path']);assert reference(path)==value,path;return path


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,
        default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))


def worker(args,plan):
    job=plan['jobs'][args.worker];query=json.loads(checked(job['query']).read_bytes())
    source=Path(plan['source']);sys.path.insert(0,str(source));os.chdir(source)
    os.environ.update(LIBERO_TYPE='standard',LIBERO_CONFIG_PATH=str(checked(plan['libero_config']).parent))
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS']=str(args.output/'private_grasp_models')
    hooks=module('default63_hooks',source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    hooks.bootstrap_source('original',evaluation='hybrid_repair');hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from scripts.probe_bounded_hybrid_repair import constructed_original_start
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    producer=module('default63_exact_train_producer',checked(plan['producer']))
    assignment=json.loads((args.output/'assignment.json').read_bytes())
    endpoints={key:HttpRpcClient(assignment[key+'_url']) for key in ('sam3','vla')}
    case=job['case'];episode=args.output/'episode';episode.mkdir()
    constructed=constructed_original_start(case,plan)
    with probe.runtime(case,endpoints,episode,domain='original',constructed_start=constructed) as (facade,adapter,policy,timings):
        trials=[]
        for repeat in range(3):
            resumed=job.get('resume_trials',{}).get(str(repeat))
            if resumed is not None:
                result=json.loads(checked(resumed).read_bytes())
                assert result['binding']==query['binding'] and result['query_id']==query['query_id']
                assert result['candidate_id']==query['candidate_id'] and result['seed']==job['seed']+repeat*1000
                trials.append({'result':result,'summary':resumed})
                continue
            result=producer.evaluate_candidate_at_saved_state(query,probe,facade,adapter,policy,
                args.output/f'trial{repeat}',job['seed']+repeat*1000)
            trials.append({'result':result,'summary':reference(args.output/f'trial{repeat}/summary.json')})
        write(args.output/'summary.json',{'query_id':query['query_id'],'record_id':query['record_id'],
            'binding':query['binding'],'trials':trials,'candidate':query['candidate'],'case':case,
            'status':'physical_result','requested_repeats':3,'registered_query':job['query'],
            'source_split':'train','training_admission':True,'training_executed':False,
            'PRO':False,'D2':False,'confirmation':False,'old_binding_preserved':True})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',type=int);args=parser.parse_args();plan=json.loads(args.manifest.read_bytes())
    assert plan['source_split']=='train' and plan['requested_repeats']==3 and not plan['training']
    if args.worker is not None:return worker(args,plan)
    source=Path(plan['source']);sys.path.insert(0,str(source));os.chdir(source)
    os.environ['PYTHONPATH']=str(source);os.environ['LIBERO_CONFIG_PATH']=str(checked(plan['libero_config']).parent)
    hooks=module('default63_services',source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    hooks.bootstrap_source('original',evaluation='hybrid_repair')
    from scripts.probe_bounded_feasibility import services
    args.output.mkdir(parents=True,exist_ok=True)
    with hooks.owned_services(SimpleNamespace(source=source,output=args.output,sam3_entry=checked(plan['sam_entry'])),services,vla=True) as endpoints:
        def run(index):
            closed=args.output/f'closed_{index:03d}.json'
            if closed.exists():checked(json.loads(closed.read_bytes()));return
            directory=args.output/f'query{index:03d}'
            if directory.exists():directory.rename(args.output/f'interrupted_{index:03d}_{time.time_ns()}')
            directory.mkdir();write(directory/'assignment.json',{key+'_url':v._base_url for key,v in endpoints.items()})
            with (directory/'worker.log').open('x') as stream:
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--manifest',str(args.manifest),
                    '--output',str(directory),'--worker',str(index)],stdout=stream,stderr=subprocess.STDOUT,check=True)
            write(closed,reference(directory/'summary.json'));print(json.dumps({'closed':index}),flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for future in as_completed([pool.submit(run,i) for i in range(len(plan['jobs']))]):future.result()


if __name__=='__main__':main()
