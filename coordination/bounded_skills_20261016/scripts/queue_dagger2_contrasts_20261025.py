"""Add the registered300 contrasts after577 model tops under one shared cap."""
from pathlib import Path
import datetime,fcntl,hashlib,json,subprocess
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025';prep=run/'dagger2_contrasts_exact/preparation'
check=json.loads((prep/'CPU_submission.json').read_bytes())
assert subprocess.check_output(['sacct','-X','-j',check['CPU_job'],'-n','-o','State'],text=True).strip()=='COMPLETED'
assert '"source_snapshots_cpu_checked": 2, "controls": 0' in (prep/'audit.log').read_text()
old=run/'unlock_queue_1300';out=run/'unlock_queue_dagger877';out.mkdir(exist_ok=False)
tasks=json.loads((old/'tasks.json').read_bytes());assert len(tasks)==32
contrast=prep/'collect.sbatch';subprocess.run(['bash','-n',str(contrast)],check=True)
extra=[{'name':'dagger2_deterministic_contrast','superseded_job':None,'script':str(contrast),'script_sha256':hashlib.sha256(contrast.read_bytes()).hexdigest(),'original_array_index':i} for i in range(10)]
tasks=tasks[:28]+extra+tasks[28:]
assert len(tasks)==42
for task in tasks:assert hashlib.sha256(Path(task['script']).read_bytes()).hexdigest()==task['script_sha256']
(out/'tasks.json').write_text(json.dumps(tasks,indent=2)+'\n')
(out/'dispatch.py').write_bytes((old/'dispatch.py').read_bytes())
s=(old/'launch.sbatch').read_text().replace(str(old),str(out)).replace('0-31%3','0-41%3').replace('rd-c3-unlock-tier5','rd-c3-dev-dagger877')
(out/'launch.sbatch').write_text(s);subprocess.run(['bash','-n',str(out/'launch.sbatch')],check=True)
test=subprocess.run(['sbatch','--test-only',str(out/'launch.sbatch')],capture_output=True,text=True,check=True)
(out/'test_only.txt').write_text(test.stdout+test.stderr)
# A changed live state aborts replacement rather than touching running work.
detail=subprocess.check_output(['scontrol','show','job','12380','-o'],text=True)
assert 'JobState=PENDING ' in detail and 'RunTime=00:00:00 ' in detail and 'JobName=rd-c3-unlock-tier5 ' in detail
states=subprocess.check_output(['squeue','-h','-j','12380','-o','%T'],text=True).splitlines();assert set(states)=={'PENDING'}
(out/'superseded_12380.json').write_text(json.dumps({'detail':detail,'control_steps':0})+'\n')
subprocess.run(['scancel','12380'],check=True)
job=subprocess.check_output(['sbatch','--parsable',str(out/'launch.sbatch')],text=True).strip()
note={'owner':'Codex3','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'array_job':job,'array':'0-41%3','independent_tasks':True,'order':{'0-8':'development five trial','9-27':'577 actual model-top train queries, one trial each','28-37':'300 deterministic train contrasts, NOT model choices, one trial each','38-41':'contact/N1/E'},'cancelled_only_own_pending':[12380],'old_GPU_steps':0,'node':'node02','nice':500,'GPU_cap':3,'CPU_cap':36,'memory_GB_cap':360,'source_tree_unchanged':'9612e31636706aef8e7eaab49528c35994002e89','C2_sidecar_legal8_pilot':job+'_0','sidecar_switch_ACK':False,'C2_service12318':'kept; no cancellation; notify separately after verified pilot and old clients drain','model_top_query_sha256':'7bc711b7da2838cfc89d7b383de01510fb455136002e108496c9a025726ff385','contrast_query_sha256':'8096198f2832560c2a1db4235390eb51ddaf13b84a313c8aac3a3aa1bd072d1f','exact_bindings_changed':False,'replacement_mapping_required':False,'CPU_contrast_binding_audit':{'job':check['CPU_job'],'real_source_snapshots':2,'controls':0},'tasks_sha256':hashlib.sha256((out/'tasks.json').read_bytes()).hexdigest(),'dispatcher_sha256':hashlib.sha256((out/'dispatch.py').read_bytes()).hexdigest(),'protected_jobs_modified':False,'training_executed':False}
(out/'registration.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n');(run/'active_queue.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 开发→577首选→300对照→回归：补齐DAgger2并保持独立三卡上限\n\n'+json.dumps(note,ensure_ascii=False)+'\n')
print(json.dumps(note,ensure_ascii=False))
