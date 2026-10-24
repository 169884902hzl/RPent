"""Prepare new-source panels without mixing the interrupted program-error cohort."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025';reg=json.loads((run/'blacklist_progress_fix_source.json').read_bytes());src=Path(reg['remote_source']);oldsrc=r/'source_failure_blacklist_9612e316_20261025';old=run/'panels5_blacklist_v1';out=run/'panels5_blacklist_r2'
assert not out.exists();shutil.copytree(old,out,copy_function=os.link,symlinks=True,ignore=shutil.ignore_patterns('results','task_board.lock'))
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for p in out.rglob('*'):
 if p.is_file() and p.suffix in {'.json','.jsonl','.md','.sbatch'} and 'common_starts' not in p.parts:
  s=p.read_text().replace(str(old),str(out)).replace(str(oldsrc),str(src)).replace(reg['base_tree'],reg['tree'])
  if p.suffix=='.json':
   d=json.loads(s)
   if isinstance(d,dict) and 'jobs' in d:
    d['source_revision']=ref(src/'SOURCE_REVISION.json');d['schema']=ref(src/'rpent/skill_package/schema.json');d['contract']=ref(src/'rpent/skill_package/contract.py');s=json.dumps(d,indent=2)+'\n'
  p.unlink();p.write_text(s)
sys.path.insert(0,str(src))
from robots.libero.bounded_task_board import update_from_results
update_from_results(out)
oldn=run/'C0_N1_blacklist_v1';newn=run/'C0_N1_progressfix';(newn/'preparation').mkdir(parents=True)
s=(oldn/'preparation/manifest.json').read_text().replace(str(oldn),str(newn)).replace(str(oldsrc),str(src)).replace(reg['base_tree'],reg['tree']);d=json.loads(s);d['source_revision']=ref(src/'SOURCE_REVISION.json');d['schema']=ref(src/'rpent/skill_package/schema.json');(newn/'preparation/manifest.json').write_text(json.dumps(d,indent=2)+'\n')
(newn/'preparation/run.sbatch').write_text((oldn/'preparation/run.sbatch').read_text().replace(str(oldn),str(newn)).replace(str(oldsrc),str(src)))
# New shared repeat uses the same registered complete initial states.
olds=run/'shared12318_pilot';news=run/'shared12318_pilot_r2';news.mkdir()
for name in ('run.py','run.sh'):
 s=(olds/name).read_text().replace(str(olds),str(news)).replace(str(oldsrc),str(src)).replace(str(old),str(out));(news/name).write_text(s)
compile((news/'run.py').read_text(),str(news/'run.py'),'exec');subprocess.run(['bash','-n',str(news/'run.sh')],check=True)
(run/'failure_blacklist_source_9612.json').write_bytes((run/'failure_blacklist_source.json').read_bytes());(run/'failure_blacklist_source.json').write_text(json.dumps(reg,indent=2)+'\n')
q=run/'unlock_queue_dagger877';tasks=json.loads((q/'tasks.json').read_bytes());(q/'tasks_before_progressfix.json').write_bytes((q/'tasks.json').read_bytes())
for task in tasks:
 if task['name'].startswith('development'):task['script']=task['script'].replace(str(old),str(out))
 if task['name']=='N1_C0':task['script']=str(newn/'preparation/run.sbatch')
 task['script_sha256']=hashlib.sha256(Path(task['script']).read_bytes()).hexdigest()
p=q/'tasks.next.json';p.write_text(json.dumps(tasks,indent=2)+'\n');p.replace(q/'tasks.json')
# Update pending sidecar launch paths; CPU hold remains until all331 checks pass.
p=q/'dispatch.py';s=p.read_text().replace(str(old),str(out)).replace("run/'panels5_blacklist_v1'","run/'panels5_blacklist_r2'");compile(s,str(p),'exec');p.write_text(s)
active=json.loads((run/'active_queue.json').read_bytes());active.pop('source_tree_unchanged',None);active.update(source_tree=reg['tree'],development_panel=str(out),shared_repeat=str(news),progressfix_CPU_job=reg['CPU_job'],tasks_sha256=ref(q/'tasks.json')['sha256'],dispatcher_sha256=ref(p)['sha256'],source_error_archive=str(olds));(run/'active_queue.json').write_text(json.dumps(active,ensure_ascii=False,indent=2)+'\n')
(run/'progressfix_preparation.json').write_text(json.dumps({'source_tree':reg['tree'],'CPU_job':reg['CPU_job'],'panel':str(out),'N1':str(newn),'shared_repeat':str(news),'held_new_tasks':list(range(1,9))+[40],'old_held_jobs_untouched':True,'program_error_cohort_kept':str(old),'physical_started':False},indent=2)+'\n')
print(json.dumps({'prepared':str(out),'source_tree':reg['tree'],'physical_started':False}))
