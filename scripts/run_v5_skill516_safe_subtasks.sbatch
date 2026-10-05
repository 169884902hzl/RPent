#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-skill516-safe
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
SKILL516_ROOT=/public/home/sunyihan/rpent_libero_eval
SKILL516_SOURCE="${SKILL516_SOURCE:?Parent must register and provide final isolated source snapshot}"
SKILL516_BASE="$SKILL516_ROOT/results/harness_v5/skill516_safe_subtask_exploration_20261005"
SKILL516_MANIFEST="${SKILL516_MANIFEST:-$SKILL516_BASE/preparation/full.json}"
SKILL516_MANIFEST_SHA="${SKILL516_MANIFEST_SHA:?Parent must provide registered manifest SHA}"
SKILL516_SHARDS="${SKILL516_SHARDS:-8}"
export PYTHONPATH="$SKILL516_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$SKILL516_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$SKILL516_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$SKILL516_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SKILL516_SOURCE"
"$SKILL516_ROOT/.venv/bin/python" - "$SKILL516_MANIFEST" "$SKILL516_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered original safe-subtask manifest changed")
PY
SKILL516_OUT="$SKILL516_BASE/exploration_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$SKILL516_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$SKILL516_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" \
  --shards "$SKILL516_SHARDS" --output "$SKILL516_OUT"
