#!/usr/bin/env bash
# Original LIBERO-90 placement method selection.  No node or
# dependency binding; failed physical trials remain in the shard ledger.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-skill535-place
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SKILL535_SOURCE:?registered isolated source snapshot required}"
MANIFEST="${SKILL535_PLACE_MANIFEST:?registered place manifest required}"
MANIFEST_SHA="${SKILL535_PLACE_MANIFEST_SHA:?registered place manifest SHA required}"
PROBE_SHA="${SKILL535_PROBE_SHA:?registered probe source SHA required}"
SHARDS="${SKILL535_SHARDS:-8}"
BASE="${SKILL535_PLACE_BASE:-$ROOT/results/harness_v5/skill535_place_selection_paths_20261006}"

export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$SOURCE" "$PROBE_SHA" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest = Path(sys.argv[1]); expected = sys.argv[2]
source = Path(sys.argv[3]); probe_expected = sys.argv[4]
if not manifest.is_absolute() or not source.is_absolute():
    raise RuntimeError("manifest and isolated source must use absolute paths")
actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
if actual != expected:
    raise RuntimeError(f"registered place manifest changed: {actual}")
probe = source / "scripts/probe_v5_skill501_original.py"
probe_sha = hashlib.sha256(probe.read_bytes()).hexdigest()
if probe_sha != probe_expected:
    raise RuntimeError(f"registered probe source changed: {probe_sha}")
plan = json.loads(manifest.read_text())
if plan.get("qualification_authorized") is not False or plan.get("new_training_rows") != 0:
    raise RuntimeError("selection manifest cannot authorize training or qualification")
if plan.get("cohort") != "selection":
    raise RuntimeError("a disjoint confirmation requires its own registered launcher")
if {case.get("kind") for case in plan.get("cases", [])} != {"place"}:
    raise RuntimeError("place launcher received a mixed manifest")
PY

# The same CPU-only command is run before submission and again before any
# GPU daemon starts.  It is independent of the current working directory.
if [[ "${SKILL535_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  "$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards "$SHARDS"
  exit 0
fi
OUT="$BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$(dirname "$OUT")"
"$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" \
  >"$BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$SOURCE"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" \
  --shards "$SHARDS" --output "$OUT"
