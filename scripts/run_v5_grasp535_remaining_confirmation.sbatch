#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp535-confirm
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${GRASP535_SOURCE:?registered source snapshot required}
GROUP=${GRASP535_GROUP:?set frypan or moka_pot}
BASE="$ROOT/results/harness_v5/grasp535_remaining_confirmation_CPU_20261005"
MANIFEST="$BASE/$GROUP/full.json"
MANIFEST_SHA=${GRASP535_MANIFEST_SHA:?registered manifest SHA required}
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"

"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
manifest, expected = Path(sys.argv[1]), sys.argv[2]
actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
if actual != expected:
    raise RuntimeError(f"registered confirmation manifest changed: {actual}")
PY

OUT="$BASE/$GROUP/confirmation_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 --output "$OUT"
