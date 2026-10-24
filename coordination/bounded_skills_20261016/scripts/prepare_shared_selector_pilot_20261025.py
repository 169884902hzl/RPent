"""Prepare the C2-offered four-CPU step; never starts before E1 completion."""
from pathlib import Path
import datetime,fcntl,hashlib,json
r=Path('/public/home/sunyihan/rpent_libero_eval');run=r/'results/bounded_skills/task_ladder_20261025';out=run/'shared12318_pilot';out.mkdir(exist_ok=False)
src=r/'source_failure_blacklist_9612e316_20261025';pkg=Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_e_20261024_1300/sidecar_legal8');shards=run/'panels5_blacklist_v1/preparation/development_shards.json'
script=f'''from pathlib import Path
import importlib.util,json,os,subprocess
r=Path({str(r)!r});out=Path({str(out)!r});src=Path({str(src)!r});pkg=Path({str(pkg)!r})
spec=importlib.util.spec_from_file_location('pilot_resource_sampler',src/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
metrics=out/'resources';metrics.mkdir()
sampler=helper.ResourceSampler(metrics);sampler.stage='shared12318_Areference_sidecar_pi_SAM_render';sampler.start()
conf=json.loads((pkg/'SIDECAR_CONFIG.json').read_bytes())
command=[conf['interpreter'],str(pkg/'source/with_selector_sidecar.py'),'--package-root',str(pkg),'--output',str(out/'selector'),'--',str(r/'.venv/bin/python'),str(r/'run_ladder_selector_shard_20261025.py'),'--source',str(src),'--shards',{str(shards)!r},'--index','1','--parallel','2','--selector-url','{{SELECTOR_ENDPOINT}}','--pilot-ack',{str(run/'sidecar_pilot_verified.json')!r},'--sidecar-package',str(pkg)]
try:result=subprocess.run(command)
finally:
 sampler.close();(metrics/'summary.json').write_text(json.dumps(sampler.summary(sampler.stage),indent=2)+chr(10))
raise SystemExit(result.returncode)
'''
compile(script,str(out/'run.py'),'exec');(out/'run.py').write_text(script)
shell=f'''#!/bin/bash
set -euo pipefail
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PYTHONPATH={src}
export PI05_CHECKPOINT_PATH={r}/assets/pi05 SAM3_CHECKPOINT_PATH={r}/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
{r}/.venv/bin/python -u {out}/run.py
'''
(out/'run.sh').write_text(shell)
record={'owner':'Codex3','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'prepared only; wait explicit E1 completion, not elapsed-time permission','C2_offer_UTC':'2026-10-24T20:54:03.685618+00:00','job':12318,'node':'node02','step_CPU_cap':4,'episode_processes':2,'own_array':12385,'own_array_throttle_during_shared_step':2,'C3_GPU_total_cap_including_shared':3,'logical_pilot':'12385_0 box five layouts, same frozen manifest and complete starts','cancel_only_own_pending_task_before_start':'12385_0','run_command':['srun','--jobid=12318','--overlap','--exact','--nodelist=node02','--nodes=1','--ntasks=1','--cpus-per-task=4','--gres=gpu:1','bash',str(out/'run.sh')],'E2_training':'C2 defers until pilot finished','same_source_tree':'9612e31636706aef8e7eaab49528c35994002e89','GPU_peak_scope':'whole shared allocation includes original A reference service plus local A selector/pi/SAM/full robot render; not normal one-A production peak','physical_started':False,'protected_jobs_modified':False,'C2_service_cancelled':False}
(out/'preparation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX);f.write('\n## Codex3 接受C2的12318共享试点窗口，已备命令，等E1实际结束信号\n\n'+json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,ensure_ascii=False))
