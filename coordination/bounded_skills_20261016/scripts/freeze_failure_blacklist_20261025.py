"""Freeze only the supported blacklist repair on the registered physical source."""
from pathlib import Path
import hashlib, json, os, re, shutil, subprocess, tarfile, tempfile
repo=Path('/home/agilex/cobot_magic/rpent_libero_eval')
base=Path('/tmp/rd_task_ladder_20261025')
out=Path('/tmp/rd_task_ladder_blacklist_r2_20261025')
assert not out.exists()
shutil.copytree(base,out,copy_function=os.link,symlinks=True)
paths=['rpent/skill_package/contract.py','SKILL_PACKAGE_SPEC.md','robots/libero/bounded_skills.py','tests/unit_tests/robots/libero/test_bounded_skills.py','tests/unit_tests/robots/libero/test_bounded_feedback.py']
new=['robots/libero/bounded_failure_history.py','tests/unit_tests/robots/libero/test_bounded_failure_history.py']
for path in paths:
    diff=subprocess.check_output(['git','diff','--',path],cwd=repo,text=True)
    prefix,*hunks=re.split(r'(?m)(?=^@@ )',diff)
    # The guided-mask cache predates this turn and remains outside its snapshot.
    kept=[h for h in hunks if '_guided_payload_responses' not in h and '_guided_payload_capture' not in h and 'current-public-image' not in h]
    patch=prefix+''.join(kept)
    target=out/path
    data=target.read_bytes();target.unlink();target.write_bytes(data)
    if path == 'SKILL_PACKAGE_SPEC.md':
        section='`episode_policy.aggressive=true`'+(repo/path).read_text().split('`episode_policy.aggressive=true`')[1].split('The earlier development-only')[0]
        target.write_text(target.read_text()+'\n## Repeated failures in aggressive episodes\n\n'+section)
        continue
    subprocess.run(['git','apply','--check','-'],input=patch,text=True,cwd=out,check=True)
    subprocess.run(['git','apply','-'],input=patch,text=True,cwd=out,check=True)
for path in new:
    shutil.copy2(repo/path,out/path)
# base is an immutable Git tree registered before this repair.
base_tree='b61f357604414fc45b2f019702a04ede6c6436d0'
with tempfile.TemporaryDirectory() as temp:
    env={**os.environ,'GIT_INDEX_FILE':str(Path(temp)/'index')}
    subprocess.run(['git','read-tree',base_tree],cwd=repo,env=env,check=True)
    for path in paths+new:
        blob=subprocess.check_output(['git','hash-object','-w',str(out/path)],cwd=repo,text=True).strip()
        subprocess.run(['git','update-index','--add','--cacheinfo',f'100644,{blob},{path}'],cwd=repo,env=env,check=True)
    tree=subprocess.check_output(['git','write-tree'],cwd=repo,env=env,text=True).strip()
archive=Path('/tmp')/f'failure_blacklist_{tree[:8]}.tgz'
with tarfile.open(archive,'w:gz') as tar:
    for path in paths+new: tar.add(out/path,arcname=path)
record={'base_tree':base_tree,'tree':tree,'local_source':str(out),'replacements':str(archive),'replacements_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'changed':{p:hashlib.sha256((out/p).read_bytes()).hexdigest() for p in paths+new},'scope':'two-failure blacklist in aggressive loop; public depth motion required to unlock','unrelated_guided_mask_cache_included':False,'training':False}
Path('/tmp/failure_blacklist_registration.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
