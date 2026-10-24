import datetime, hashlib, json, pathlib, subprocess
root=pathlib.Path('/public/home/sunyihan/rpent_libero_eval')
run=root/'results/bounded_skills/task_ladder_20261025'
out=run/'unlock_queue_1300'
out.mkdir(exist_ok=True)
specs=[('development_box',12374,run/'panels5_v4/preparation/C0-box5-scope4.sbatch',[None]),('development_rest',12375,run/'panels5_v4/preparation/dev-v4-tier5.sbatch',list(range(8))),('dagger2',12314,run/'dagger2_exact/preparation/collect.sbatch',list(range(19))),('contact',12376,run/'contact_scope5_r4/paired5.sbatch',[None]),('N1_old',12308,root/'results/bounded_skills/option_expansion_20261025/preparation/N1_legacy_b96_r2.sbatch',[None]),('N1_C0',12377,run/'C0_N1_v4/preparation/run.sbatch',[None]),('N1_geometry',12368,root/'results/bounded_skills/option_expansion_20261025/preparation/N1_geometry_0bc4633f_r2.sbatch',[None])]
tasks=[]; old=[]
for name,job,script,indices in specs:
    detail=subprocess.check_output(['scontrol','show','job',str(job),'-o'],text=True)
    assert 'JobState=PENDING ' in detail and 'RunTime=00:00:00 ' in detail and 'JobName=rd-c3-' in detail,(job,detail)
    assert 'ReqNodeList=node02 ' in detail and 'Nice=500 ' in detail
    old.append({'job':job,'detail':detail})
    subprocess.run(['bash','-n',str(script)],check=True)
    for index in indices:
        tasks.append({'name':name,'superseded_job':job,'script':str(script),'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'original_array_index':index})
(out/'tasks.json').write_text(json.dumps(tasks,indent=2)+'\n')
worker='''import hashlib,json,os,pathlib,subprocess
p=pathlib.Path(__file__).parent
i=int(os.environ['SLURM_ARRAY_TASK_ID'])
task=json.loads((p/'tasks.json').read_text())[i]
script=pathlib.Path(task['script'])
assert hashlib.sha256(script.read_bytes()).hexdigest()==task['script_sha256']
env=dict(os.environ)
if task['original_array_index'] is not None:
    env['SLURM_ARRAY_TASK_ID']=str(task['original_array_index'])
print(json.dumps({'dispatch_array_index':i,'task':task}),flush=True)
raise SystemExit(subprocess.call(['bash',str(script)],env=env))
'''
(out/'dispatch.py').write_text(worker)
compile(worker,str(out/'dispatch.py'),'exec')
script=f'''#!/bin/bash
#SBATCH --job-name=rd-c3-unlock-tier5
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=120G
#SBATCH --time=12:00:00
#SBATCH --array=0-{len(tasks)-1}%3
#SBATCH --output={out}/job-%A_%a.log
set -euo pipefail
{root}/.venv/bin/python -u {out}/dispatch.py
'''
(out/'launch.sbatch').write_text(script)
subprocess.run(['bash','-n',str(out/'launch.sbatch')],check=True)
test=subprocess.run(['sbatch','--test-only',str(out/'launch.sbatch')],capture_output=True,text=True,check=True)
(out/'test_only.txt').write_text(test.stdout+test.stderr)
(out/'superseded_pending.json').write_text(json.dumps(old,indent=2)+'\n')
# Only these freshly checked, never-started C3 jobs are replaced.
subprocess.run(['scancel',*[str(s[1]) for s in specs]],check=True)
job=subprocess.check_output(['sbatch','--parsable',str(out/'launch.sbatch')],text=True).strip()
record={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'job':job,'tasks':len(tasks),'array_throttle':3,'order':['development5','DAgger2','contact_and_N1'],'independent_array_tasks':True,'noncausal_dependencies':False,'cancelled_only_own_pending':[s[1] for s in specs],'running_jobs_cancelled':[],'protected_jobs_modified':False,'node':'node02','nice':500,'max_CPU':36,'max_memory_GB':360,'tasks_sha256':hashlib.sha256((out/'tasks.json').read_bytes()).hexdigest()}
(out/'registration.json').write_text(json.dumps(record,indent=2)+'\n')
coord=pathlib.Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
import fcntl
with coord.open('a') as f:
    fcntl.flock(f,fcntl.LOCK_EX)
    f.write('\n## Codex3 13:00补充：独立任务按解锁顺序重排，共享三卡上限\n\n'+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,ensure_ascii=False))
