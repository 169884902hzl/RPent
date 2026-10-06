#!/usr/bin/env bash
# Run box52/mug100 after the separate main-harness smoke dependency passes.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp-infra-repair
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${GRASP_REPAIR_SOURCE:?registered source snapshot required}"
MANIFEST="${GRASP_REPAIR_MANIFEST:?absolute box52 or mug100 manifest required}"
MANIFEST_SHA="${GRASP_REPAIR_MANIFEST_SHA:?registered manifest SHA required}"
PROBE_SHA="${GRASP_REPAIR_PROBE_SHA:?registered probe SHA required}"
BASE="${GRASP_REPAIR_OUTPUT_BASE:-$ROOT/results/harness_v5/grasp_infrastructure_repair_20261006}"
SHARDS="${GRASP_REPAIR_SHARDS:-8}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$PROBE_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
for path, expected in ((Path(sys.argv[1]), sys.argv[2]),
                       (Path("scripts/probe_v5_grasp449_20261005.py"), sys.argv[3])):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"registered grasp input changed: {path}: {actual}")
PY
"$ROOT/.venv/bin/python" -m scripts.v5_probe_preflight --manifest "$MANIFEST" \
  --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --states
OUT="$BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_grasp449_20261005 \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --output "$OUT"
