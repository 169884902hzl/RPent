"""Freeze priority1 jobs; use the third card after the actual pilot closes."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('/public/home/sunyihan/rpent_libero_eval')
run=root/'results/bounded_skills/next_b_pi_first_20261023'
base=run/'train_dagger_once_priority1'
prep=base/'preparation'
entries=run/'entry_snapshots'

def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def freeze(path):
    target=entries/(ref(path)['sha256']+path.suffix)
    if target.exists():assert target.read_bytes()==path.read_bytes()
    else:target.write_bytes(path.read_bytes())
    return ref(target)

entry=freeze(root/'run_train_dagger_once_20261023.py')
producer=freeze(root/'evaluate_bounded_training_candidate_20261023.py')
exporter=freeze(root/'export_train_dagger_once_CPU_20261023.py')
helper=freeze(root/'export_onpolicy_measurements_CPU_20261023.py')
prompt=freeze(root/'export_original_schema6_measured_final_CPU_20261022.py')
register=freeze(root/'register_train_dagger_packet_CPU_20261023.py')
count=0
for index in range(1,62):
    source=prep/f'shard{index:03d}.json';plan=json.loads(source.read_bytes())
    plan.update(entry=entry,measurement_producer=producer,measurement_exporter=exporter,
        measurement_helper=helper,prompt_helper=prompt,registration_entry=register,
        parent_manifest=ref(source))
    target=prep/f'bulk_shard{index:03d}.json'
    with target.open('x') as f:json.dump(plan,f,indent=2)
    count+=len(plan['jobs'])
assert count==1931
script=prep/'bulk_once.sbatch'
text=f'''#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-train-dagger-priority1
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=08:00:00
#SBATCH --output={root}/results/slurm-%A_%a.log
set -euo pipefail
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PI05_CHECKPOINT_PATH={root}/assets/pi05 SAM3_CHECKPOINT_PATH={root}/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export LIBERO_CONFIG_PATH={root}/runtime_config_original_20261023
TASK=$(printf '%03d' "$SLURM_ARRAY_TASK_ID")
MANIFEST={prep}/bulk_shard$TASK.json
OUTPUT={base}/shard$TASK
EXPORT={base}/exports/shard${{TASK}}_job${{SLURM_ARRAY_JOB_ID}}_${{SLURM_ARRAY_TASK_ID}}
{root}/.venv/bin/python -u {entry['path']} --manifest "$MANIFEST" --output "$OUTPUT"
{root}/.venv/bin/python {exporter['path']} --source {root}/source_pi_first_origin_f6ce1d46_20261023 --manifest "$MANIFEST" --results "$OUTPUT" --policy-hashes {root}/results/bounded_skills/execution_repairs_20261022/qualified90_9716b68c/preparation/registered_pi05_hashes.sha256 --measurement-helper {helper['path']} --prompt-helper {prompt['path']} --output "$EXPORT"
{root}/.venv/bin/python {register['path']} --package "$EXPORT" --name C3_DAGGER_ONCE_shard${{TASK}}_job${{SLURM_ARRAY_JOB_ID}}_${{SLURM_ARRAY_TASK_ID}}
'''
with script.open('x') as f:f.write(text)
job=subprocess.check_output(['sbatch','--parsable','--array=1-61%1',
    '--dependency=afterok:11717',str(script)],text=True).strip()
metadata={'job':job,'remaining_queries':count,'array':'1-61%1',
    'dependency':'after successful pilot11717; third card while two main evaluations run, raise throttle only as they finish',
    'entry':entry,'producer':producer,'exporter':exporter,'helper':helper,'prompt_helper':prompt,
    'registration_entry':register,'script':ref(script),
    'maximum_C3_GPU_after_main_jobs':3,'training':False,'collection_repeats':1}
with (prep/'bulk_submission.json').open('x') as f:json.dump(metadata,f,indent=2)
print(json.dumps(metadata))
