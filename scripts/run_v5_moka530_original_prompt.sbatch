#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-moka530-prompt
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
MOKA530_ROOT=/public/home/sunyihan/rpent_libero_eval
MOKA530_SOURCE="${MOKA530_SOURCE:?Registered isolated source required}"
MOKA530_BASE="$MOKA530_ROOT/results/harness_v5/moka530_initial_pose_prompt_original_20261005"
MOKA530_MANIFEST="$MOKA530_BASE/preparation/probe.json"
MOKA530_MANIFEST_SHA="${MOKA530_MANIFEST_SHA:?Registered manifest SHA required}"
export PYTHONPATH="$MOKA530_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$MOKA530_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$MOKA530_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$MOKA530_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$MOKA530_SOURCE"
"$MOKA530_ROOT/.venv/bin/python" - "$MOKA530_MANIFEST" "$MOKA530_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered original prompt diagnostic changed")
PY
MOKA530_OUT="$MOKA530_BASE/probe_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$MOKA530_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MOKA530_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 --output "$MOKA530_OUT"
