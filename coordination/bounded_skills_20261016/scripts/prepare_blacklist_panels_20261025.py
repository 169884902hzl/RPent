"""Prepare fresh, immutable-input panels after the blacklist CPU closure."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,shutil,subprocess
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025'
reg=json.loads((run/'failure_blacklist_source.json').read_bytes());src=Path(reg['remote_source'])
assert subprocess.check_output(['sacct','-X','-j',reg['CPU_job'],'-n','-o','State'],text=True).strip()=='COMPLETED'
assert '329 passed' in (run/'CPU_failure_blacklist.log').read_text()
old=run/'panels5_v4';out=run/'panels5_blacklist_v1'
assert not out.exists()
shutil.copytree(old,out,copy_function=os.link,symlinks=True)
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
oldsrc=r/'source_ladder_scope_b61f3576_20261025'
for p in out.rglob('*'):
 if p.is_file() and p.suffix in {'.json','.jsonl','.md','.sbatch'} and 'common_starts' not in p.parts:
  text=p.read_text().replace(str(old),str(out)).replace(str(oldsrc),str(src)).replace(reg['base_tree'],reg['tree'])
  if p.suffix=='.json':
   value=json.loads(text)
   if isinstance(value,dict) and 'jobs' in value:
    value['source_revision']=ref(src/'SOURCE_REVISION.json')
    value['schema']=ref(src/'rpent/skill_package/schema.json')
    value['contract']=ref(src/'rpent/skill_package/contract.py')
    value['failure_blacklist']='same skill+parameters twice; confirmed physical scene change required'
    text=json.dumps(value,indent=2)+'\n'
  p.unlink();p.write_text(text)
# Preserve all old N1 output; use the same complete common initial states.
oldn1=run/'C0_N1_v4';n1=run/'C0_N1_blacklist_v1';(n1/'preparation').mkdir(parents=True)
d=json.loads((oldn1/'preparation/manifest.json').read_bytes())
def repl(value):
 if isinstance(value,str):return value.replace(str(oldn1),str(n1)).replace(str(oldsrc),str(src)).replace(reg['base_tree'],reg['tree'])
 if isinstance(value,list):return [repl(x) for x in value]
 if isinstance(value,dict):return {k:repl(v) for k,v in value.items()}
 return value
d=repl(d);d['source_revision']=ref(src/'SOURCE_REVISION.json');d['schema']=ref(src/'rpent/skill_package/schema.json')
(n1/'preparation/manifest.json').write_text(json.dumps(d,indent=2)+'\n')
s=(oldn1/'preparation/run.sbatch').read_text().replace(str(oldn1),str(n1)).replace(str(oldsrc),str(src))
(n1/'preparation/run.sbatch').write_text(s)
# No pending jobs are canceled or requeued; only their versioned dispatch map changes.
queue=run/'unlock_queue_1300';tasks=json.loads((queue/'tasks.json').read_bytes())
assert 'PENDING' in subprocess.check_output(['squeue','-h','-j','12380','-o','%T'],text=True)
for task in tasks:
 if task['name'].startswith('development'):
  task['script']=task['script'].replace(str(old),str(out))
 elif task['name']=='N1_C0':task['script']=str(n1/'preparation/run.sbatch')
 task['script_sha256']=hashlib.sha256(Path(task['script']).read_bytes()).hexdigest()
(queue/'tasks_before_blacklist.json').write_bytes((queue/'tasks.json').read_bytes())
temp=queue/'tasks.next.json';temp.write_text(json.dumps(tasks,indent=2)+'\n');temp.replace(queue/'tasks.json')
note={'owner':'Codex3','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_tree':reg['tree'],'source':str(src),'CPU':{'node02':'329 passed 149.37s','local':'329 passed 181.67s'},'development_panel':str(out),'N1_C0':str(n1),'queue':12380,'old_outputs_preserved':True,'DAgger_frozen_sources_unchanged':True,'schema_fields_changed':False,'public_legality_version':'public-request-legal/8','contract_sha256':ref(src/'rpent/skill_package/contract.py')['sha256'],'schema9_sha256':ref(src/'rpent/skill_package/schema9.json')['sha256'],'schema10_sha256':ref(src/'rpent/skill_package/schema10.json')['sha256'],'physical_results':False,'protected_jobs_modified':False}
(run/'blacklist_active.json').write_text(json.dumps(note,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 黑名单CPU闭合；开发与N1使用新版本目录，旧数据保留\n\n'+json.dumps(note,ensure_ascii=False)+'\n')
print(json.dumps(note))
