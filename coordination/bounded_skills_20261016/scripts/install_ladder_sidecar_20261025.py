# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Install only C3 queue dispatch wiring; preserve C2's delivered package."""
from pathlib import Path
import hashlib,json,subprocess
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025';queue=run/'unlock_queue_1300';board=run/'panels5_blacklist_v1'
pkg=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_e_20261024_1300')
for name,digest in {'with_selector_sidecar.py':'c970665e5370ad495dd5d69d0e756af92f10664b80119f80154ad9ac49235eee','serve_selector_sidecar.py':'cb2207be5ddb8be7f58424abf341b19b60fa5c0c652e3ecf74e6dc53f543fff7'}.items():
 assert hashlib.sha256((pkg/'source'/name).read_bytes()).hexdigest()==digest
config=json.loads((pkg/'SIDECAR_CONFIG.json').read_bytes());assert config['adapter_sha256']=='5825fe0f4a29a268483413e6af07fb67be542df6b9477b5e79156749eb4efa26'
# Save old dispatcher and replace atomically before any GPU task starts.
assert set(subprocess.check_output(['squeue','-h','-j','12380','-o','%T'],text=True).splitlines())=={'PENDING'}
(queue/'dispatch_before_sidecar.py').write_bytes((queue/'dispatch.py').read_bytes())
worker='''from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys
r=Path('/public/home/sunyihan/rpent_libero_eval');q=Path(__file__).parent;run=q.parent
i=int(os.environ['SLURM_ARRAY_TASK_ID']);task=json.loads((q/'tasks.json').read_bytes())[i]
script=Path(task['script']);assert hashlib.sha256(script.read_bytes()).hexdigest()==task['script_sha256']
env=dict(os.environ)
if task['original_array_index'] is not None:env['SLURM_ARRAY_TASK_ID']=str(task['original_array_index'])
print(json.dumps({'dispatch_array_index':i,'task':task}),flush=True)
use_sidecar=task['name'].startswith('development') and (i==0 or (run/'sidecar_switch_ACK.json').exists())
sampler=None
if use_sidecar:
    board=run/'panels5_blacklist_v1';pkg=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_e_20261024_1300')
    conf=json.loads((pkg/'SIDECAR_CONFIG.json').read_bytes())
    src=Path(json.loads((run/'failure_blacklist_source.json').read_bytes())['remote_source'])
    shards=board/'preparation'/('development_shards.json' if i==0 else 'development_remaining_shards.json')
    index=1 if i==0 else task['original_array_index']
    log=run/'sidecar_jobs'/f'{os.environ["SLURM_ARRAY_JOB_ID"]}_{i}'
    spec=importlib.util.spec_from_file_location('shared_sampler',src/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    metrics=run/'sidecar_resources'/f'{os.environ["SLURM_ARRAY_JOB_ID"]}_{i}';metrics.mkdir(parents=True)
    sampler=helper.ResourceSampler(metrics);sampler.stage='sidecar_pi_SAM_render';sampler.start()
    command=[conf['interpreter'],str(pkg/'source/with_selector_sidecar.py'),'--package-root',str(pkg),'--output',str(log),'--',
        str(r/'.venv/bin/python'),str(r/'run_ladder_selector_shard_20261025.py'),'--source',str(src),'--shards',str(shards),'--index',str(index),'--selector-url','{SELECTOR_ENDPOINT}']
else:command=['bash',str(script)]
try:
    result=subprocess.run(command,env=env)
finally:
    if sampler is not None:
        sampler.close();(metrics/'summary.json').write_text(json.dumps(sampler.summary('sidecar_pi_SAM_render'),indent=2)+'\\n')
if result.returncode:raise SystemExit(result.returncode)
if use_sidecar and i==0:
    subprocess.run([sys.executable,str(r/'check_ladder_sidecar_shard_20261025.py'),'--source',str(src),'--shards',str(shards),'--index',str(index),'--ack',str(run/'sidecar_switch_ACK.json')],check=True)
'''
compile(worker,str(queue/'dispatch.py'),'exec')
p=queue/'dispatch.next.py';p.write_text(worker);p.replace(queue/'dispatch.py')
print(json.dumps({'pilot':'12380_0','after_ACK':'remaining development uses local sidecar; before ACK retains12318','package_untouched':True,'GPU_jobs_cancelled':False,'first_shard_peak_scope':'selector+pi05+SAM3+render, sampled whole allocated GPU','dispatcher_sha256':hashlib.sha256((queue/'dispatch.py').read_bytes()).hexdigest()}))
