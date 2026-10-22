from pathlib import Path
import subprocess,json,shlex,hashlib
R=Path('/public/home/sunyihan/rpent_libero_eval')
B=R/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
O=B/'measured_anchor_efa57340';S=R/'source_measured_vla_efa57340_20261023'
records=[]
for name,depends,mem,argv in [
 ('N2','11560','32G',[str(R/'.venv/bin/python'),str(R/'aggregate_measured_v7_CPU_20261023.py'),'--run',str(O),'--panel','N2','--output',str(O/'CPU_N2')]),
 ('155','11561:11562','96G',[str(R/'.venv/bin/python'),str(R/'aggregate_measured_v7_CPU_20261023.py'),'--run',str(O),'--panel','155','--output',str(O/'CPU_155')]),
 ('N1','11563','24G',[str(R/'.venv/bin/python'),str(R/'aggregate_strict_latency_v7_CPU_20261023.py'),'--source',str(S),'--before',str(B/'N1_native_complete_baseline_c752/formal'),'--after',str(O/'N1'),'--output',str(O/'CPU_N1'),'--indices',*map(str,list(range(24))+list(range(26,32)))])]:
 p=O/'preparation'/('close_'+name+'_CPU.sbatch')
 content=f'''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=2
#SBATCH --mem={mem}
#SBATCH --time=02:00:00
#SBATCH --output={R}/results/slurm-%j.log
set -euo pipefail
export PYTHONPATH={S}
export CUDA_VISIBLE_DEVICES=''
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export LIBERO_CONFIG_PATH={R}/runtime_config_original_20261023
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
exec {shlex.join(argv)}
'''
 with p.open('x') as f:f.write(content)
 cmd=['sbatch','--parsable','--job-name=rd-c3-v7-close-'+name,'--dependency=afterok:'+depends,str(p)]
 job=subprocess.check_output(cmd,text=True).strip().split(';')[0]
 records.append({'job':job,'phase':name,'command':cmd,'script_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
with (O/'CPU_close_submissions_r1.json').open('x') as f:json.dump(records,f,indent=2)
print(json.dumps(records))
