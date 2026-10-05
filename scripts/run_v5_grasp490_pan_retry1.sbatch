#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-3%2
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp490-pan
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp490_pan_retry1_20261005"
BASE="$ROOT/results/harness_v5/grasp490_pan_retry1_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/preparation/full.json" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != "7f53e64c71ab6c74309424e6ec2a819c57495417c1c9c92bd1b861dac63eee1c":
    raise RuntimeError("registered four-arm pan discovery changed")
PY
OUT="$BASE/full_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/full.json" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 --output "$OUT"
