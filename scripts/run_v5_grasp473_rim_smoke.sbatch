#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=01:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp473-rim
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp473_measured_rim_20261005"
BASE="$ROOT/results/harness_v5/grasp473_measured_rim_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$BASE/preparation/smoke.json" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != "a973a75913040c4d7f011aa07dc02ae156a4afb9244cd10896969c02a5067c03":
    raise RuntimeError("registered12-case measured-rim comparison changed")
PY
OUT="$BASE/smoke_job${SLURM_JOB_ID}"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/smoke.json" --shard-index 0 --shards 1 --output "$OUT"
"$ROOT/.venv/bin/python" scripts/summarize_v5_grasp449_20261005.py \
  --manifest "$BASE/preparation/smoke.json" --ledger "$OUT/episodes.jsonl" --output "$OUT/report.json"
