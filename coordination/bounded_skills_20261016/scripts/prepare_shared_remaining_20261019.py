"""Register remaining originals and D2 only after the shared-launcher study passes."""
import argparse
import hashlib
import itertools
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'coordination/bounded_skills_20261016'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def queue():
    return [line.split('|') for line in subprocess.check_output(
        ['squeue','-r','-h','-u','sunyihan','-o','%i|%j|%T|%N|%R|%b'],text=True).splitlines()]


def build(args):
    study=json.loads((args.study_output/'study_summary.json').read_bytes())
    assert study['adoption_ready'] and study['throughput_improved']
    assert study['consistency']['all_three_within_serial_baseline']
    n=study['selected_n']
    assert n>=4 and study['source_commit']=='ec89f74'
    args.output.mkdir(parents=True,exist_ok=False)
    receipts=[BASE/'reports'/name for name in (
        'original20_support_roundrobin_20261018_full_submission.json',
        'original20_roundrobin_cancel_repair_20261018_full_submission.json')]
    submitted=[json.loads(path.read_bytes()) for path in receipts]
    original=submitted[0]
    for value in submitted:
        assert all(value[key]==original[key] for key in ('manifest','snapshot','source_commit'))
    assert sha(original['manifest']['path'])==original['manifest']['sha256']
    plan=json.loads(Path(original['manifest']['path']).read_bytes())
    rows=queue()
    active={row[0] for row in rows if row[2]=='RUNNING'}
    completed,running,remaining=[],[],[]
    results=ROOT/'results/bounded_skills/feasibility_20261017'
    for i,case in enumerate(plan['cases']):
        records=[]
        active_jobs=[]
        for receipt in submitted:
            if i not in receipt['indices']:
                continue
            job=f"{receipt['job']}_{i}"
            if job in active:
                active_jobs.append(job)
            ledger=results/('job'+job)/'episodes.jsonl'
            if ledger.exists():
                for line in ledger.read_bytes().splitlines(keepends=True):
                    if line.endswith(b'\n'):
                        row=json.loads(line)
                        if row.get('status')=='physical_result':
                            assert row['case']==case and row['arm']=='oracle_k4' and row['pi05_calls']==0
                            records.append({'job':job,'record':str(ledger),'success':row['success']})
        assert len(records)<=1,(i,records)
        if records:
            completed.append({'index':i,'case':case['name'],**records[0]})
        elif active_jobs:
            running.append({'index':i,'case':case['name'],'jobs':active_jobs})
        else:
            remaining.append(i)
    d2=json.loads((BASE/'reports/hybrid_d2_75ce7d53_startup_submission_20261019.json').read_bytes())
    assert d2['source_commit'].startswith('75ce7d53')
    assert sha(d2['manifest']['path'])==d2['manifest']['sha256']
    d2_plan=json.loads(Path(d2['manifest']['path']).read_bytes())
    assert len(d2_plan['cases'])==40 and not d2_plan['training'] and not d2_plan['confirmation']
    domains=[('original',original,remaining),('d2',d2,list(range(40)))]
    grouped=[]
    for domain,ref,indices in domains:
        source=ref.get('snapshot',ref.get('source'))
        assert source and Path(source).is_absolute()
        grouped.append([{'domain':domain,'source':source,'source_commit':ref['source_commit'],
            'manifest':ref['manifest'],'indices':indices[start:start+2*n]}
            for start in range(0,len(indices),2*n)])
    batches=[batch for group in itertools.zip_longest(*grouped) for batch in group if batch]
    production={'selected_n':n,'batches':batches,'training':False,'confirmation':False,
        'study_output':str(args.study_output),'study_summary_sha256':sha(args.study_output/'study_summary.json'),
        'already_completed':completed,'already_running_naturally':running,
        'selection':'all uncompleted original indices; no filtering by task success; all 40 D2 registered cases'}
    write_new(args.output/'batch_plan.json',production)
    startup={'selected_n':min(n,4),'batches':[],'training':False,'confirmation':False}
    study_launch=json.loads((args.study_output/'launch.json').read_bytes())
    for domain,ref,indices in domains:
        if indices:
            batch=next(batch for batch in batches if batch['domain']==domain)
            # Startup is an interface check, not a new cohort result. Keep
            # the same registered original smoke states already exercised
            # by the throughput study, and the first two fixed D2 cases.
            startup_indices=study_launch['indices'][:4] if domain=='original' else indices[:2]
            startup['batches'].append({**batch,'indices':startup_indices})
    startup['scope']='physical interface startup only; excluded from original220 and D2 outcome counts'
    write_new(args.output/'startup_plan.json',startup)
    launcher=BASE/'scripts/shared_gpu_episodes_20261019.py'
    frozen=ROOT/('launcher_shared_20261019_'+sha(launcher)[:12])
    frozen.mkdir(exist_ok=True)
    for name in (launcher.name,'run_shared_batch_20261019.sbatch'):
        target=frozen/name
        if target.exists():
            assert target.read_bytes()==(BASE/'scripts'/name).read_bytes()
        else:
            shutil.copy2(BASE/'scripts'/name,target)
    for label,value in [('batch',production),('startup',startup)]:
        for index,batch in enumerate(value['batches']):
            command=[str(ROOT/'.venv/bin/python'),str(frozen/launcher.name),
                '--batch-plan',str(args.output/(label+'_plan.json')),'--batch-index',str(index),'--preflight']
            checked=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,
                env=dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),
                    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
            (args.output/f'{label}_{index}_preflight.log').write_text(checked.stdout+checked.stderr)
            checked.check_returncode()
    # Cancellation is separate from preparation: do it only once the pinned
    # per-domain real startups have succeeded and production is submitted.
    report={'launcher_directory':str(frozen),'launcher_sha256':sha(frozen/launcher.name),
        'source_commits':{domain:ref['source_commit'] for domain,ref,_ in domains},
        'original_remaining_indices':remaining,'original_completed':len(completed),
        'original_running':running,'d2_cases':40,'selected_n':n,'batches':len(batches),
        'startup_batches':len(startup['batches']),'replacement_arrays':[ref['job'] for ref in submitted]+[d2['job']],
        'cpu_per_job':20,'memory_per_job':'140G','max_gpu':4,
        'node':'node02','nice':500,'preflight':'passed','production_submitted':False}
    write_new(args.output/'preparation.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-output',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args())
