#!/usr/bin/env bash
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_visual_binding6_20261001"
SHARED="$ROOT/results/harness_v5/original_training1_660_20261001/job2840_task0"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
OUT="$ROOT/results/harness_v5/paired_collection_plain_init10_20261001/step_${SLURM_JOB_ID}_${SLURM_STEP_ID}"
"$ROOT/.venv/bin/python" - "$SOURCE" "$SHARED" "$OUT" <<'PY'
import re,subprocess,sys
from pathlib import Path
source,shared,out=map(Path,sys.argv[1:])
endpoints={}
for name in ('sam3','vla'):
 text=(shared/f'shared_{name}.log').read_text()
 matches=re.findall(r'RPC server listening on (http://127\.0\.0\.1:\d+)',text)
 if not matches:raise RuntimeError(f'{name} is not ready')
 endpoints[name]=matches[0]
command=[sys.executable,'-u',str(source/'harness_v5_eval.py'),'--suite','libero_10','--task','0','--seed','10','--provider','oracle','--max-decisions','100','--max-chunks','80','--max-episode-steps','10000','--choice-package','/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a','--sam3-endpoint',endpoints['sam3'],'--vla-endpoint',endpoints['vla'],'--output-dir',str(out)]
subprocess.run(command,check=True)
PY
