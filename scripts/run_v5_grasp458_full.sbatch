#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-23%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp458-full
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp458_stop_20261005"
BASE="$ROOT/results/harness_v5/grasp458_stop_aperture_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/smoke_job3520/report.json" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1]))
if not report["complete"] or report["recorded"] != 24:
    raise RuntimeError("required24-case instrument smoke is incomplete")
if any(row["counts"].get("execution_error", 0) or row["counts"].get("runtime_exception", 0)
       for row in report["by_condition_group"].values()):
    raise RuntimeError("unrepaired instrument failure cannot start the100/class experiment")
if any(row["known_truth"] != row["recorded"]
       for row in report["sustained_truth_methods"].values()):
    raise RuntimeError("private sustained-truth instrument is incomplete")
PY
exec "$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/full.json" \
  --shard-index "$SLURM_ARRAY_TASK_ID" --shards 24 \
  --output "$BASE/full_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
