"""Pin the evaluated v7 executor plus the explicit human capability amendment."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

repo=Path(__file__).resolve().parents[3]
base='2db200134ea6689e36a66e8aee6f45daa8270b4e'
with tempfile.TemporaryDirectory(prefix='c3-nextb-') as temp:
    source=Path(temp)
    archive=subprocess.check_output(['git','archive',base],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(source,filter='data')
    names=['robots/libero/bounded_skills.py','robots/libero/bounded_offline_labels.py','rpent/skill_package/contract.py']
    patch=subprocess.check_output(['git','diff','ff352fc4^','ff352fc4','--',*names],cwd=repo)
    subprocess.run(['git','apply','-'],input=patch,cwd=source,check=True)
    schema=subprocess.check_output(['git','show','ff352fc4:rpent/skill_package/schema7.json'],cwd=repo)
    (source/'rpent/skill_package/schema7.json').write_bytes(schema)
    (source/'rpent/skill_package/schema.json').write_bytes(schema)
    changed=[*names,'rpent/skill_package/schema7.json','rpent/skill_package/schema.json']
    for name in ['scripts/probe_bounded_hybrid_d2.py','coordination/bounded_skills_20261016/scripts/original_model_closedloop_20261021.py']:
        # Keep the evaluated executor; only the registered-state evaluation
        # entrypoints come from this working change.
        (source/name).write_bytes((repo/name).read_bytes());changed.append(name)
    index=source/'temporary.index'
    import os
    env={**os.environ,'GIT_INDEX_FILE':str(index)}
    subprocess.run(['git','read-tree',base],cwd=repo,env=env,check=True)
    for name in changed:
        blob=subprocess.check_output(['git','hash-object','-w',str(source/name)],cwd=repo,text=True).strip()
        subprocess.run(['git','update-index','--add','--cacheinfo',f'100644,{blob},{name}'],cwd=repo,env=env,check=True)
    tree=subprocess.check_output(['git','write-tree'],cwd=repo,env=env,text=True).strip()
    target=repo/f'rd_next_b_eval_{tree[:8]}_20261023.tar.gz'
    subprocess.run(['git','archive','--format=tar.gz','-o',str(target),tree],cwd=repo,check=True)
    registration={'base_evaluated_tree':base,'tree':tree,'archive':str(target),
        'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'changes':changed,'excludes_unrelated_dirty':True,'schema_version':'bounded-skills/7',
        'legality_version':'public-request-legal/5'}
    out=repo/'coordination/bounded_skills_20261016/reports/next_b_pi_first_20261023'
    out.mkdir(exist_ok=True)
    (out/('source_registration_'+tree[:8]+'.json')).write_text(json.dumps(registration,indent=2)+'\n')
    print(json.dumps(registration))
