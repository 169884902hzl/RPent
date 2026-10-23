"""Queue priority1's first32 once, only after the owned model mirror releases."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('/public/home/sunyihan/rpent_libero_eval')
run=root/'results/bounded_skills/next_b_pi_first_20261023'
out=run/'train_dagger_once_priority1/preparation'
plan=out/'shard000.json'
def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
data=json.loads(plan.read_bytes());assert len(data['jobs'])==32 and data['requested_repeats']==1
pilot={**data,'pilot_parent_manifest':ref(plan),
    'entry':ref(root/'run_train_dagger_once_20261023.py'),
    'measurement_exporter':ref(root/'export_train_dagger_once_CPU_20261023.py')}
manifest=out/'pilot32.json'
with manifest.open('x') as f:json.dump(pilot,f,indent=2)
script=out/'pilot32.sbatch'
text=f'''#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-train-dagger-once-pilot32
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=06:00:00
#SBATCH --output={root}/results/slurm-%j.log
set -euo pipefail
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PI05_CHECKPOINT_PATH={root}/assets/pi05 SAM3_CHECKPOINT_PATH={root}/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export LIBERO_CONFIG_PATH={root}/runtime_config_original_20261023
{root}/.venv/bin/python -u {root}/run_train_dagger_once_20261023.py --manifest {manifest} --output {run}/train_dagger_once_priority1/pilot32
'''
with script.open('x') as f:f.write(text)
job=subprocess.check_output(['sbatch','--parsable','--dependency=afterany:11713',str(script)],text=True).strip()
metadata={'job':job,'dependency':'owned model mirror11713 release after all model cases closed',
    'manifest':ref(manifest),'entry':pilot['entry'],'script':ref(script),
    'physical_repeats':1,'training_executed':False,'priority1_order_preserved':True,
    'GPU_concurrency':'2 oracle workers plus pilot <=3 after mirror exits'}
with (out/'pilot32_submission.json').open('x') as f:json.dump(metadata,f,indent=2)
print(json.dumps(metadata))
