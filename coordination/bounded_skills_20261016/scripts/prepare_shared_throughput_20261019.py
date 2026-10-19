"""Freeze launcher bytes and register the workload before running the study."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
BASE=ROOT/'coordination/bounded_skills_20261016'
reports=BASE/'reports'
old=json.loads((reports/'original20_support_roundrobin_20261018_preparation.json').read_bytes())
manifest=Path(old['manifest']['path'])
assert hashlib.sha256(manifest.read_bytes()).hexdigest()==old['manifest']['sha256']
plan=json.loads(manifest.read_bytes())
assert len(plan['cases'])==220 and plan['source_commit']=='ec89f74'
source=Path(old['snapshot'])
indices=[seed*11+offset for seed in range(8) for offset in (0,2,10)]
assert [plan['cases'][i]['category'] for i in indices[:3]]==['bowl_transfer','container','stove_on']
cohort_path=reports/'original20_support_interim_r18_20261019.json'
cohort=json.loads(cohort_path.read_bytes())
by_name={row['case']['name']:row for row in cohort['cohort']['rows']}
consistency=[]
for index in indices[:3]:
    case=plan['cases'][index]
    row=by_name[case['name']]
    assert row['status']=='physical_result' and row['case']==case
    choices,=Path(row['record']).parent.glob('*oracle_k4/choices.jsonl')
    consistency.append({'case':case,'choices':{'path':str(choices),
        'sha256':hashlib.sha256(choices.read_bytes()).hexdigest()},
        'historical_result':{key:row[key] for key in ('success','decisions','sim_steps','wall_s')},
        'historical_source_commit':cohort['source_commit']})
launcher=BASE/'scripts/shared_gpu_episodes_20261019.py'
sha=hashlib.sha256(launcher.read_bytes()).hexdigest()
frozen=ROOT/('launcher_shared_20261019_'+sha[:12])
frozen.mkdir()
for filename in ('shared_gpu_episodes_20261019.py','run_shared_gpu_episodes_20261019.sbatch'):
    shutil.copy2(BASE/'scripts'/filename,frozen/filename)
preparation=ROOT/'results/bounded_skills/shared_throughput_20261019/preparation'
preparation.mkdir(parents=True,exist_ok=True)
study=preparation/'throughput_study_r1.json'
registration={'source':str(source),'source_commit':plan['source_commit'],'manifest':old['manifest'],
    'indices':indices,'cases':[plan['cases'][i] for i in indices],
    'selection':'three fixed categories bowl/container/stove-on, official init0-7; no selection by success',
    'consistency_cases':consistency,'plateau_fraction':.10,
    'levels':[1,4,8,12],'conditional_extra_levels':[16,20],
    'selection_rule':'smallest N within 10% of best measured parallel throughput; require measured improvement',
    'consistency_rule':'parallel choice edit distance, final success and sim-step differences each <= fresh-serial baseline',
    'startup':'same launcher, four isolated cases to first physical request before full levels',
    'launcher_sha256':sha,'gpu_per_job':1,'cpu_per_job':20,'memory_per_job':'140G',
    'candidate_concurrency':'serial','training':False,'confirmation':False}
with study.open('x') as stream:json.dump(registration,stream,indent=2);stream.write('\n')
command=[str(ROOT/'.venv/bin/python'),str(frozen/launcher.name),'--source',str(source),
    '--manifest',str(manifest),'--indices',','.join(map(str,indices)),'--levels','1,4,8,12',
    '--study-plan',str(study),'--preflight']
environment=dict(os.environ,PYTHONPATH=str(source),SOURCE_COMMIT=plan['source_commit'],
    LIBERO_TYPE='standard',LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),CUDA_VISIBLE_DEVICES='',
    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
checked=subprocess.run(command,cwd=source,env=environment,capture_output=True,text=True)
log=preparation/'preflight_study_r1.log';log.write_text(checked.stdout+checked.stderr)
checked.check_returncode()
report={'source':str(source),'source_commit':plan['source_commit'],'manifest':old['manifest'],
    'study_plan':{'path':str(study),'sha256':hashlib.sha256(study.read_bytes()).hexdigest()},
    'launcher_directory':str(frozen),
    'launcher_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir()},
    'preflight':{'exit_code':checked.returncode,'log':str(log),'command':command},
    'case_indices':indices,'physical_evidence':'not yet submitted','training':False}
with (reports/'shared_throughput_r1_preparation_20261019.json').open('x') as stream:
    json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(report),flush=True)
