from pathlib import Path
import json,subprocess,os
R=Path('/public/home/sunyihan/rpent_libero_eval')
B=R/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/measured_anchor_efa57340'
S=R/'source_measured_vla_efa57340_20261023'
pre=B/'preparation'
headers='''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --gres=gpu:1
#SBATCH --time=18:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
'''
init=f'''ROOT={R}
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export SCHEMA6_SOURCE={S}
export SOURCE_COMMIT=efa57340221c82cb359d72514c7062edb34de599
export SCHEMA6_LIBERO_CONFIG_PATH=$ROOT/runtime_config_original_20261023
export SCHEMA6_CONCURRENCY=8
'''
body=init+f'''export SCHEMA6_MANIFEST={pre}/smoke10.json
export SCHEMA6_OUTPUT={B}/smoke10
bash "$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"
export SCHEMA6_MANIFEST={pre}/pilot3.json
export SCHEMA6_OUTPUT={B}/pilot3
exec bash "$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"
'''
p=pre/'run_smoke_pilot.sbatch'
with p.open('x') as f:f.write(headers+body)
for shard in range(2):
 p=pre/f'run155_{shard}.sbatch'
 with p.open('x') as f:f.write(headers+init+f'''export SCHEMA6_MANIFEST={pre}/shard{shard}.json
export SCHEMA6_OUTPUT={B}/formal155_shard{shard}
exec bash "$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"
''')
# N1 is serial within one GPU, with the registered complete canonical state.
p=pre/'run_N1.sbatch'
with p.open('x') as f:f.write(headers+init+f'''export LIBERO_CONFIG_PATH=$SCHEMA6_LIBERO_CONFIG_PATH
export PI05_CHECKPOINT_PATH=$ROOT/assets/pi05 SAM3_CHECKPOINT_PATH=$ROOT/assets/sam3/sam3.pt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec "$ROOT/.venv/bin/python" -u "$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py" --source "$SCHEMA6_SOURCE" --manifest {pre}/N1.json --output {B}/N1 --common-starts {B.parent}/fulltask124c5654/native_complete_common_starts --initial-mode restore --indices {' '.join(map(str,list(range(24))+list(range(26,32))))}
''')
p=pre/'run_N2.sbatch'
with p.open('x') as f:f.write(headers+init+f'''export SCHEMA6_MANIFEST={pre}/N2.json
export SCHEMA6_OUTPUT={B}/N2
exec bash "$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch"
''')
# Pure CPU extraction is independent of the pending physical pilot.
text=f'''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=4
#SBATCH --mem=40G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH={R}/runtime_config_original_20261023
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
exec {R}/.venv/bin/python {R}/prepare_measured_vla_v7_20261023.py --source {S} --n2
'''
p=pre/'prepare_N2_CPU.sbatch'
with p.open('x') as f:f.write(text)
job=subprocess.check_output(['sbatch','--parsable','--job-name=rd-c3-v7-N2-CPU',str(p)],text=True).strip()
with (B/'N2_CPU_submission.json').open('x') as f:json.dump({'job':job,'script':str(p),'GPU':False},f,indent=2)
print(job)
