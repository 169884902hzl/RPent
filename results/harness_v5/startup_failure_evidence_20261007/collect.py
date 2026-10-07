"""Collect only explicitly named old logs and ledgers for startup diagnosis."""

import hashlib
import json
import subprocess
from pathlib import Path


REMOTE = r'''
import collections,hashlib,json,subprocess
from pathlib import Path
root=Path('/public/home/sunyihan/rpent_libero_eval')
records=[]
for job in (4355,4369,4378):
    for part in range(8):
        log=root/'results'/f'slurm-{job}_{part}.log'
        log_ref={'path':str(log),'exists':log.exists()}
        if log.exists():
            raw=log.read_bytes();lines=raw.decode(errors='replace').splitlines()
            log_ref.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                original_excerpt=[{'line':i+1,'text':line} for i,line in enumerate(lines)
                    if i>=50],log_has_startup_error_text=any('startup_error' in line for line in lines))
        if job==4355:
            ledger=root/'results/harness_v5/interim574_20261007/A3-N'/f'job{job}'/f'part{part}/probe/episodes.jsonl'
        else:
            ledger=root/'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/smoke10'/f'job{job}'/f'part{part}/probe/episodes.jsonl'
        ledger_ref={'path':str(ledger),'exists':ledger.exists()}
        episodes=[]
        if ledger.exists():
            raw=ledger.read_bytes();rows=[json.loads(line) for line in raw.decode().splitlines()]
            ledger_ref.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),rows=len(rows))
            for row in rows:
                result=row.get('result',{})
                episodes.append({'episode':row.get('episode'),'case_name':row.get('case',{}).get('name'),
                    'result_status':result.get('status'),'result_error':result.get('error'),
                    'top_error':row.get('error'),'server_chunk_execution':row.get('server_chunk_execution'),
                    'source_hash_paths':result.get('source_hash_paths'),
                    'private_final_done':row.get('private_after',{}).get('done'),
                    'finalizer_error':row.get('post_finalizer_error')})
        records.append({'job':job,'part':part,'log':log_ref,'ledger':ledger_ref,'episodes':episodes})
source=root/'source_v5_drawer571_20261006/harness_v5_eval.py'
raw=source.read_bytes();lines=raw.decode().splitlines()
source_evidence={'path':str(source),'sha256':hashlib.sha256(raw).hexdigest(),
    'finalizer_excerpt':[{'line':i+1,'text':lines[i]} for i in list(range(936,941))+list(range(967,973))],
    'root_typed_choice_eval_exists':(source.parent/'typed_choice_eval.py').exists(),
    'registered_supplement_path':str(root/'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/typed_choice_eval.py'),
    'registered_supplement_exists':(root/'results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/typed_choice_eval.py').exists()}
sacct=subprocess.run(['sacct','-j','4355,4369,4378','--format=JobID,State,ExitCode,Elapsed,NodeList','-n','-P'],
    check=True,capture_output=True,text=True).stdout
print(json.dumps({'read_mode':'explicit_log_and_ledger_paths_no_directory_enumeration',
    'sacct_original':sacct,'records':records,'source571_finalizer':source_evidence},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    directory=Path(__file__).parent
    report=directory/'report.json'
    if report.exists():
        raise SystemExit('Keep the existing evidence report.')
    run=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                       input=REMOTE,text=True,capture_output=True,check=True)
    payload=json.loads(run.stdout)
    repo=directory.parents[2]
    current_files=('v5_batch_eval.py','scripts/run_v5_interim574.sbatch',
                   'scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch',
                   'scripts/probe_v5_moka_transfer_public_20261007.py','harness_v5_eval.py',
                   'coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch')
    payload['current_local_code_refs']=[{'path':str((repo/name).resolve()),
        'sha256':hashlib.sha256((repo/name).read_bytes()).hexdigest()} for name in current_files]
    payload['current_local_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    report.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    for job in (4355,4369,4378):
        records=[r for r in payload['records'] if r['job']==job]
        rows=[e for r in records for e in r['episodes']]
        print(json.dumps({'job':job,'recorded_rows':len(rows),'status_counts':{
            k:sum(e['result_status']==k for e in rows) for k in set(e['result_status'] for e in rows)},
            'requested_controls':sum(int((e['server_chunk_execution'] or {}).get('requested_controls',0)) for e in rows)},
            ensure_ascii=False))
