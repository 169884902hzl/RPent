#!/usr/bin/env bash
# Independent original LIBERO-90 articulate confirmation.  This launcher is
# deliberately separate from the 511/516 smoke launchers and has no node or
# dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-skill535-articulate
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SKILL535_SOURCE:?registered isolated source snapshot required}"
MANIFEST="${SKILL535_ARTICULATE_MANIFEST:?registered articulate manifest required}"
MANIFEST_SHA="${SKILL535_ARTICULATE_MANIFEST_SHA:?registered articulate manifest SHA required}"
PROBE_SHA="${SKILL535_PROBE_SHA:?registered probe source SHA required}"
SHARDS="${SKILL535_SHARDS:-8}"
BASE="${SKILL535_ARTICULATE_BASE:-$ROOT/results/harness_v5/skill535_articulate_confirmation_20261005}"

export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"

"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$SOURCE" "$PROBE_SHA" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest = Path(sys.argv[1]); expected = sys.argv[2]
source = Path(sys.argv[3]); probe_expected = sys.argv[4]
actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
if actual != expected:
    raise RuntimeError(f"registered articulate manifest changed: {actual}")
probe = source / "scripts/probe_v5_skill501_original.py"
probe_sha = hashlib.sha256(probe.read_bytes()).hexdigest()
if probe_sha != probe_expected:
    raise RuntimeError(f"registered probe source changed: {probe_sha}")
plan = json.loads(manifest.read_text())
if plan.get("qualification_authorized") is not False or plan.get("new_training_rows") != 0:
    raise RuntimeError("confirmation manifest cannot authorize training or qualification")
if {case.get("kind") for case in plan.get("cases", [])} != {"articulate"}:
    raise RuntimeError("articulate launcher received a mixed manifest")
PY

OUT="$BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$(dirname "$OUT")"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" \
  --shards "$SHARDS" --output "$OUT"
