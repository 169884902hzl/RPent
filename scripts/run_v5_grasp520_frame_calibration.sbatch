#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=06:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp520-sync
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
GRASP520_ROOT=/public/home/sunyihan/rpent_libero_eval
GRASP520_SOURCE="${GRASP520_SOURCE:?Parent must provide isolated source supporting private_frame_sync}"
GRASP520_BASE="$GRASP520_ROOT/results/harness_v5/grasp520_original_frame_calibration_20261005"
GRASP520_MANIFEST="${GRASP520_MANIFEST:-$GRASP520_BASE/preparation/pilot.json}"
GRASP520_MANIFEST_SHA="${GRASP520_MANIFEST_SHA:?Parent must provide explicit registered manifest SHA}"
export PYTHONPATH="$GRASP520_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$GRASP520_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$GRASP520_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$GRASP520_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$GRASP520_SOURCE"
"$GRASP520_ROOT/.venv/bin/python" - "$GRASP520_MANIFEST" "$GRASP520_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered original frame-calibration manifest changed")
PY
GRASP520_OUT="$GRASP520_BASE/diagnostic_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$GRASP520_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$GRASP520_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 --output "$GRASP520_OUT"
