"""Freeze the reproduced missing-policy-variable fix, preserving the base snapshot."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tarfile,tempfile
repo=Path('/home/agilex/cobot_magic/rpent_libero_eval');base=Path('/tmp/rd_task_ladder_blacklist_r2_20261025');source=Path('/tmp/rd_task_ladder_blacklist_r3_20261025')
assert not source.exists();shutil.copytree(base,source,copy_function=os.link,symlinks=True)
name='robots/libero/bounded_skills.py';p=source/name;s=p.read_text();needle='        published = self.memory.apply(candidates)';assert s.count(needle)==1;s=s.replace(needle,"        aggressive = feedback_fields.get('episode_policy', {}).get('aggressive', False)\n"+needle);p.unlink();p.write_text(s)
name2='tests/unit_tests/robots/libero/test_bounded_feedback.py';p=source/name2;p.unlink();shutil.copy2(repo/name2,p)
base_tree='9612e31636706aef8e7eaab49528c35994002e89'
with tempfile.TemporaryDirectory() as tmp:
 env={**os.environ,'GIT_INDEX_FILE':str(Path(tmp)/'index')};subprocess.run(['git','read-tree',base_tree],cwd=repo,env=env,check=True)
 for name in (name,name2):
  blob=subprocess.check_output(['git','hash-object','-w',str(source/name)],cwd=repo,text=True).strip();subprocess.run(['git','update-index','--add','--cacheinfo',f'100644,{blob},{name}'],cwd=repo,env=env,check=True)
 tree=subprocess.check_output(['git','write-tree'],cwd=repo,env=env,text=True).strip()
archive=Path('/tmp')/f'blacklist_progress_fix_{tree[:8]}.tgz'
with tarfile.open(archive,'w:gz') as out:
 for name in ('robots/libero/bounded_skills.py',name2):out.add(source/name,arcname=name)
reg={'base_tree':base_tree,'tree':tree,'source':str(source),'archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ('robots/libero/bounded_skills.py',name2)},'scope':'restore aggressive local for actual exhausted progress branch; no failure-memory bypass restored','CPU_reproduction':'both aggressive=False/True exhausted request fail with same NameError before fix; pass after','contract_changed':False,'program_error_source_preserved':base_tree}
Path('/tmp/blacklist_progress_fix_registration.json').write_text(json.dumps(reg,indent=2)+'\n');print(json.dumps(reg))
