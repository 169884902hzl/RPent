#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=03:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-place527-rgbd
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
PLACE527_ROOT=/public/home/sunyihan/rpent_libero_eval
PLACE527_SOURCE="${PLACE527_SOURCE:?Registered isolated source snapshot required}"
PLACE527_BASE="$PLACE527_ROOT/results/harness_v5/place527_dual_rgbd_original_20261005"
PLACE527_MANIFEST="$PLACE527_BASE/preparation/probe.json"
PLACE527_MANIFEST_SHA="${PLACE527_MANIFEST_SHA:?Registered manifest SHA required}"
export PYTHONPATH="$PLACE527_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$PLACE527_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$PLACE527_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$PLACE527_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$PLACE527_SOURCE"
"$PLACE527_ROOT/.venv/bin/python" - "$PLACE527_MANIFEST" "$PLACE527_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered placement RGB-D manifest changed")
PY
PLACE527_OUT="$PLACE527_BASE/probe_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$PLACE527_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$PLACE527_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" \
  --shards 4 --output "$PLACE527_OUT"
