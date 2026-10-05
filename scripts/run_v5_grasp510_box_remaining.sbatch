#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp510-box-remaining
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp510_box_remaining_20261005"
BASE="$ROOT/results/harness_v5/grasp510_box_remaining_20261005"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/preparation/remaining52.json" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != "cd93583d546deb434c6233ab57367f8c510098ac3e8430b88478a33290a6f48a":
    raise RuntimeError("registered four-class independent confirmation changed")
PY
OUT="$BASE/remaining_job${SLURM_JOB_ID}/part2"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/remaining52.json" --shard-index 0 --shards 1 --output "$OUT"
