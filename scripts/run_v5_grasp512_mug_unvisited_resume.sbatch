#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp512-mug-resume
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp512_mug_unvisited_resume_20261005"
BASE="$ROOT/results/harness_v5/grasp512_mug_unvisited_resume_20261005"
export PYTHONPATH="$SOURCE" PYTHONDONTWRITEBYTECODE=1 MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/preparation/registration.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
registration = json.loads(Path(sys.argv[1]).read_text())
for key in ("original_manifest", "visited_ledger", "resume_manifest", "patched_truth"):
    item = registration[key]
    if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
        raise RuntimeError(f"registered {key} changed")
if registration["visited"] != 21 or registration["remaining_unvisited"] != 79:
    raise RuntimeError("registered unvisited continuation changed")
PY
exec "$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/resume.json" --shard-index 0 --shards 1 \
  --output "$BASE/resume_job${SLURM_JOB_ID}/part0"
