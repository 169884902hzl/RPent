"""Preserve lower-priority development work while releasing six GPUs."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OUTPUT=ROOT/'coordination/subtask_selection_interruption_for_contact_20261009.json'


def main():
    if OUTPUT.exists():raise ValueError('interruption already recorded')
    records=[]
    base=ROOT/'results/harness_v5/perturb_skill_selection_20261009_r1/vla_subtask_bottle'
    for part in range(2,8):
        job=f'4923_{part}'
        state=subprocess.run(['squeue','-h','-j',job,'-o','%T|%N'],text=True,capture_output=True,check=True).stdout.strip()
        if not state.startswith('RUNNING|'):
            records.append({'job':job,'state':state,'action':'no_running_job_to_cancel'});continue
        output=base/'job4923'/f'part{part}'/'probe'
        ledger=output/'episodes.jsonl'
        completed=[json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
        cases=[r['case']['name'] for r in completed]
        record={'job':job,'state_before':state,'completed_cases':cases,'completed_count':len(cases),
            'ledger':{'path':str(ledger),'sha256_before_cancellation':hashlib.sha256(ledger.read_bytes()).hexdigest() if ledger.exists() else None},
            'current_uncompleted_trial':'human_aborted_development_only',
            'training_allowed':False,'confirmation':False,'reason':'latest A3 and contact-method selection take priority',
            'output_preserved':str(output),'pending_selection_cases_must_resume_after_contact_selection':True}
        records.append(record)
    payload={'time_pdt':datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
             'requested_release_gpus':6,'records':records,'all_prior_records_preserved':True}
    OUTPUT.write_text(json.dumps(payload,indent=2)+'\n')
    targets=[r['job'] for r in records if r.get('state_before','').startswith('RUNNING|')]
    if targets:subprocess.run(['scancel',*targets],check=True)
    payload['scancel_requested']=targets;OUTPUT.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload))


if __name__=='__main__':main()
