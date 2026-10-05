#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=03:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp525-runtime
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
GRASP525_ROOT=/public/home/sunyihan/rpent_libero_eval
GRASP525_SOURCE="${GRASP525_SOURCE:?Parent must register the final runtime source snapshot}"
GRASP525_BASE="$GRASP525_ROOT/results/harness_v5/grasp525_first4_runtime_smoke_20261005"
GRASP525_MANIFEST="$GRASP525_BASE/preparation/smoke.json"
GRASP525_MANIFEST_SHA="${GRASP525_MANIFEST_SHA:?Parent must supply the registered smoke manifest SHA}"
export PYTHONPATH="$GRASP525_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$GRASP525_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$GRASP525_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$GRASP525_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$GRASP525_SOURCE"
"$GRASP525_ROOT/.venv/bin/python" - "$GRASP525_MANIFEST" "$GRASP525_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered runtime grasp smoke manifest changed")
PY
GRASP525_OUT="$GRASP525_BASE/probe_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$GRASP525_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$GRASP525_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" \
  --shards 4 --output "$GRASP525_OUT"
