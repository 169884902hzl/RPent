"""Submit startup or full shared-service arrays from an audited preparation."""
import argparse
import itertools
import json
import os
import subprocess
from pathlib import Path


ROOT=Path('/public/home/sunyihan/rpent_libero_eval')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--domain',choices=('original','d2'),
        help='Admit a domain as soon as its own real startup has passed')
    args=parser.parse_args()
    root=args.preparation.resolve(strict=True)
    prep=json.loads((root/'preparation.json').read_bytes())
    mode='full' if args.full else 'startup'
    receipt=root/(mode+('_'+args.domain if args.domain else '')+'_submission.json')
    assert not receipt.exists(),'Use existing submission receipt'
    plan_path=root/('batch_plan.json' if args.full else 'startup_plan.json')
    plan=json.loads(plan_path.read_bytes())
    startup_proofs=[]
    if args.full:
        domain_receipt=root/f'startup_{args.domain}_submission.json'
        startup_path=domain_receipt if args.domain and domain_receipt.exists() else root/'startup_submission.json'
        startup=json.loads(startup_path.read_bytes())
        startup_plan=json.loads((root/'startup_plan.json').read_bytes())
        for index,batch in enumerate(startup_plan['batches']):
            if args.domain and batch['domain']!=args.domain:
                continue
            job=startup['job']+'_'+str(index)
            state=subprocess.check_output(['sacct','-X','-n','-j',job,
                '--format=State,ExitCode','-P'],text=True).strip()
            assert state=='COMPLETED|0:0',(job,state)
            directory=ROOT/'results/bounded_skills/shared_remaining_20261019'/('job'+job)
            level=directory/f'N{startup_plan["selected_n"]}'
            summary=json.loads((level/'summary.json').read_bytes())
            rows=[json.loads(line) for line in (level/'episodes.jsonl').open()]
            assert summary['worker_errors']==0 and len(rows)==len(batch['indices'])
            assert all(row['process_exit_code']==0 and row['result']['status']=='startup_physical' for row in rows)
            physical=list(level.glob('*/**/first_physical*_request.json'))
            assert len(physical)==len(rows),(job,len(physical),len(rows))
            startup_proofs.append({'job':job,'state_exit':state,'summary':str(level/'summary.json'),
                'physical_requests':[str(path) for path in physical]})
    queue=[line.split('|') for line in subprocess.check_output(
        ['squeue','-r','-h','-u','sunyihan','-o','%i|%j|%T|%N|%R|%b'],text=True).splitlines()]
    c2=[row for row in queue if row[1].startswith(('rd-bounded-choice-','rd-c2-'))
        and row[2] in {'RUNNING','PENDING'} and 'gpu' in row[5].lower()]
    cap=3 if c2 else 4
    active=[row for row in queue if row[1].startswith('rd-bounded-')
        and not row[1].startswith('rd-bounded-choice-') and row[2]=='RUNNING']
    assert len(active)<=4 and all(row[3]=='node02' for row in active)
    dependency=('?'.join('afterany:'+':'.join(row[0] for row in group)
        for group in itertools.combinations(active,len(active)-cap+1)) if len(active)>=cap else None)
    indices=[i for i,batch in enumerate(plan['batches']) if not args.domain or batch['domain']==args.domain]
    assert indices and (not args.full or startup_proofs)
    throttle=max(1,min(len(indices),cap-len(active)))
    arguments=['sbatch','--parsable','--nodelist=node02','--nice=500','--export=ALL',
        '--array='+','.join(map(str,indices))+'%'+str(throttle),
        *(['--dependency='+dependency] if dependency else []),
        str(Path(prep['launcher_directory'])/'run_shared_batch_20261019.sbatch')]
    env=dict(os.environ,BATCH_PLAN=str(plan_path),
        LAUNCHER=str(Path(prep['launcher_directory'])/'shared_gpu_episodes_20261019.py'),
        STARTUP='0' if args.full else '1')
    job=subprocess.check_output(arguments,cwd=ROOT,env=env,text=True).strip().split(';')[0]
    report={'job':job,'mode':mode,'domain':args.domain,'indices':indices,'command':arguments,'plan':str(plan_path),
        'launcher_directory':prep['launcher_directory'],'source_commits':prep['source_commits'],
        'aggregate_cap':cap,'startup_proofs':startup_proofs,'codex2_gpu':c2,
        'cpu_per_job':20,'memory_per_job':'140G','training':False,'confirmation':False}
    with receipt.open('x') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
