"""Retry zero-control infrastructure starts with matched diagnostic code."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PREVIOUS = ROOT/'results/harness_v5/perturb_changed_goal_selection_20261009_r2'
OUTPUT = ROOT/'results/harness_v5/perturb_changed_goal_selection_20261009_r3'
SOURCE = ROOT/'source_v5_contact_methods_20261009_r1'
ADAPTER = ROOT/'coordination/perturb_contact_methods_adapter_20261009_r1'


def ref(path):
    return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    snapshot=json.loads((SOURCE/'source_snapshot.json').read_text())
    launcher=ADAPTER/'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    for registration in sorted(PREVIOUS.glob('*/preparation/startup_submission.json')):
        cell=registration.parent.parent.name
        prep=OUTPUT/cell/'preparation'
        if (prep/'startup_submission.json').exists():
            continue
        old=json.loads(registration.read_text())
        old_plan=Path(old['manifest']['path'])
        plan=json.loads(old_plan.read_text())
        if ref(old_plan)!=old['manifest']:
            raise ValueError('prior plan changed')
        job=str(old['job']).split(';')[0]
        ledger=registration.parent.parent/('job'+job)/'part0/probe/episodes.jsonl'
        if not ledger.exists():
            raise ValueError('missing failed startup ledger')
        rows=[json.loads(x) for x in ledger.read_text().splitlines()]
        if len(rows)!=1:
            raise ValueError('unexpected startup attempts')
        row=rows[0]
        stages=[*row.get('setup',[]),*([row['first_attempt']] if row.get('first_attempt') else [])]
        controls=sum(int(stage.get('receipt',{}).get('sim_steps_used',0)) for stage in stages)
        if not any('unexpected keyword argument' in stage.get('receipt', {}).get('error', '')
                   for stage in stages) and row.get('status') != 'infrastructure_error':
            print(json.dumps({'cell':cell,'prior_job':job,'status':'separate_binding_or_skill_repair_required',
                              'prior_status':row.get('status')}),flush=True)
            continue
        prep.mkdir(parents=True,exist_ok=False)
        plan.update(source_path=str(SOURCE),adapter_path=str(ADAPTER),source_snapshot=snapshot,
            producer=ref(Path(__file__)), producer_dependencies=[ref(Path(__file__)),
                ref(ADAPTER/'scripts/probe_v5_skill501_original.py'),
                ref(ADAPTER/'scripts/probe_v5_perturb_skill_20261009.py')],
            references=[*plan['references'],ref(old_plan),ref(ledger)],
            supersedes_startup={'job':job,'ledger':ref(ledger), 'physical_controls':controls,
                'reason':'diagnostic chunk keyword mismatch; prior setup/motion and fault preserved'})
        manifest=prep/'selection.json';manifest.write_text(json.dumps(plan,indent=2)+'\n')
        env={'PERTURB_SKILL_PLAN':str(manifest),'PERTURB_SKILL_PLAN_SHA':ref(manifest)['sha256'],
            'PERTURB_SKILL_SOURCE':str(SOURCE),'PERTURB_SKILL_ADAPTER':str(ADAPTER),
            'PERTURB_SKILL_OUTPUT':str(OUTPUT/cell),'PERTURB_SKILL_STARTUP':'1'}
        cpu=subprocess.run(['bash',str(launcher)],text=True,capture_output=True,
            env={**os.environ,**env,'PERTURB_SKILL_CPU_ONLY':'1'})
        (prep/'CPU_preflight.log').write_text(cpu.stdout+cpu.stderr);cpu.check_returncode()
        result=subprocess.run(['sbatch','--parsable','--array=0','--nice=2000',
            '--export=ALL,'+','.join(k+'='+v for k,v in env.items()),str(launcher)],
            text=True,capture_output=True,check=True)
        job_new=result.stdout.strip()
        (prep/'startup_submission.json').write_text(json.dumps({'job':job_new,'environment':env,
            'launcher':ref(launcher),'manifest':ref(manifest),'CPU_preflight':'pass',
            'superseded_startup_job':job,'physical_startup':'pending','confirmation':False},indent=2)+'\n')
        print(json.dumps({'cell':cell,'job':job_new,'superseded':job}),flush=True)


if __name__=='__main__':main()
