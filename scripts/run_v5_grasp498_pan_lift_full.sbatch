#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
# Eight one-GPU shards may use all currently free cards; no node binding.
#SBATCH --array=0-1%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp498-lift
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp498_pan_lift_comparison_20261005"
BASE="$ROOT/results/harness_v5/grasp498_pan_lift_comparison_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/preparation/full.json" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != "a9046091f39c5df74e7096945d87dd3fc5a3158afb98cc5e9fdee55c1e92c71a":
    raise RuntimeError("registered trial-lift comparison changed")
PY
OUT="$BASE/full_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/full.json" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 2 --output "$OUT"
