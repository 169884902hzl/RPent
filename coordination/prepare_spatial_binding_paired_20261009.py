"""Pin the single candidate-priority fix on the same ten spatial episodes."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
PARENT=ROOT/'source_v5_skill_budget_20261009_r2'
SOURCE=ROOT/'source_v5_runtime_transfer_binding_20261009_r1'
OLD_PREP=ROOT/'results/harness_v5/skill_budget_20261009_r2/preparation/A3-N'
OUTPUT=ROOT/'results/harness_v5/spatial_transfer_binding_A3_paired10_20261009_r1'
PREP=OUTPUT/'preparation/A3-N'


def ref(path):return {'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parent=json.loads((PARENT/'source_snapshot.json').read_text())
    if ref(Path(parent['archive']['path']))!=parent['archive']:
        raise ValueError('parent changed')
    shutil.copytree(PARENT,SOURCE,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
    changed=['robots/libero/v5_public_transfer_reference.py','robots/libero/v5_subtasks.py',
             'tests/unit_tests/robots/libero/test_v5_public_transfer_reference.py','harness_v5_eval.py']
    for rel in changed[:-1]:shutil.copy2(ROOT/rel,SOURCE/rel)
    entry=SOURCE/'harness_v5_eval.py'
    text=entry.read_text()
    anchor='                    view_axes=scene.view_axes,\n                ) if getattr(args, "vla_subtask_v1", True) else []'
    if text.count(anchor)!=1:raise ValueError('macro caller anchor changed')
    text=text.replace(anchor,'                    view_axes=scene.view_axes,\n'
        '                    instruction_transfer_binding_v1=getattr(args, "instruction_transfer_binding_v1", False),\n'
        '                ) if getattr(args, "vla_subtask_v1", True) else []')
    text=text.replace('    parser.add_argument("--wrist-refine-v1", action="store_true")',
        '    parser.add_argument("--instruction-transfer-binding-v1", action="store_true")\n'
        '    parser.add_argument("--wrist-refine-v1", action="store_true")')
    entry.write_text(text)
    with tarfile.open(parent['archive']['path']) as tar:members=list(dict.fromkeys([*tar.getnames(),*changed]))
    archive=Path(str(SOURCE)+'.tar')
    with tarfile.open(archive,'x') as tar:
        for rel in members:tar.add(SOURCE/rel,arcname=rel,recursive=False)
    with tarfile.open(archive) as tar:
        for rel in changed:
            if hashlib.sha256(tar.extractfile(rel).read()).hexdigest()!=ref(SOURCE/rel)['sha256']:
                raise ValueError('archive mismatch')
    names=[r.get('relative_path') or str(Path(r['path']).relative_to(PARENT)) for r in parent['files']]
    snapshot={'path':str(SOURCE),'commit':parent['commit'],'archive':ref(archive),
        'parent_snapshot':ref(PARENT/'source_snapshot.json'),'archive_complete':True,
        'files':[{**ref(SOURCE/rel),'relative_path':rel} for rel in dict.fromkeys([*names,*changed])],
        'purpose':'only public transfer reference candidate priority; budget and old renderer unchanged'}
    (SOURCE/'source_snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    old_index=json.loads((OLD_PREP/'manifest.json').read_text())
    all_plans=[json.loads(p.read_text()) for p in sorted(OLD_PREP.glob('A3-N_part*.json'))]
    episodes=sorted([e for plan in all_plans for e in plan['episodes'] if e['suite']=='libero_spatial_task'],
                    key=lambda e:(e['task'],e['seed']))
    if len(episodes)!=10:raise ValueError('expected same task0..4/init40,41')
    PREP.mkdir(parents=True,exist_ok=False)
    files=[]
    for part,episode in enumerate(episodes):
        plan=copy.deepcopy(all_plans[0])
        plan.update(source_path=str(SOURCE),source_commit=snapshot['commit'],episodes=[episode],
            purpose='public source-target candidate priority paired development; no new contact method',
            paired_baseline=ref(ROOT/'artifacts/skill_budget_A3N80_complete_20261009_r1/episodes.jsonl'))
        plan['budget']['instruction_transfer_binding_v1']=True
        path=PREP/f'A3-N_part{part}.json';path.write_text(json.dumps(plan,indent=2)+'\n');files.append(ref(path))
    launcher=SOURCE/'scripts/run_v5_interim574.sbatch'
    index={**old_index,'files':files,'source_path':str(SOURCE),'source_commit':snapshot['commit'],
        'source_snapshot':snapshot,'planned':{'A3-N':10},'launcher':ref(launcher),
        'references':[*old_index['references'],ref(OLD_PREP/'manifest.json')],
        'batch_runner':ref(SOURCE/'v5_batch_eval.py'), 'confirmation':False,'training_allowed':False}
    index['runtime_supplement']=[]
    path=PREP/'manifest.json';path.write_text(json.dumps(index,indent=2)+'\n')
    env={'INTERIM574_SOURCE':str(SOURCE),'INTERIM574_PREP':str(PREP),'INTERIM574_COHORT':'A3-N',
         'INTERIM574_OUTPUT_ROOT':str(OUTPUT),'INTERIM574_STARTUP_PREFLIGHT':'1'}
    cpu=subprocess.run(['bash',str(launcher)],env={**os.environ,**env,'INTERIM574_PREFLIGHT_ONLY':'1'},
                       capture_output=True,text=True)
    (PREP/'cpu_preflight.log').write_text(cpu.stdout+cpu.stderr);cpu.check_returncode()
    job=subprocess.run(['sbatch','--parsable','--nice=0','--array=0',
        '--export=ALL,'+','.join(k+'='+v for k,v in env.items()),str(launcher)],
        capture_output=True,text=True,check=True).stdout.strip()
    (PREP/'startup_submission.json').write_text(json.dumps({'job':job,'environment':env,
        'launcher':str(launcher),'manifest':ref(path),'same_baseline_episodes':True},indent=2)+'\n')
    print(json.dumps({'job':job,'episodes':10,'source':str(SOURCE),'manifest':ref(path)}))


if __name__=='__main__':main()
