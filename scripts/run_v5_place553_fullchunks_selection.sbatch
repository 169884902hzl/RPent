#!/usr/bin/env bash
# CPU prepare must pass first. Original selection only; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-place553-selection
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${PLACE553_SOURCE:?pinned full-block source required}"
MANIFEST="${PLACE553_MANIFEST:?registered same40 manifest required}"
MANIFEST_SHA="${PLACE553_MANIFEST_SHA:?manifest SHA required}"
SHARDS="${PLACE553_SHARDS:-8}"
BASE="${PLACE553_BASE:?independent output base required}"

export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$SOURCE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest, source = Path(sys.argv[1]), Path(sys.argv[3])
if not manifest.is_absolute() or not source.is_absolute():
    raise ValueError("manifest and source require absolute paths")
if hashlib.sha256(manifest.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("registered manifest changed")
plan = json.loads(manifest.read_text())
if plan.get("cohort") != "selection" or plan.get("qualification_authorized") is not False or plan.get("new_training_rows") != 0:
    raise ValueError("this launcher never grants confirmation or training admission")
if len(plan["cases"]) != 40 or {case["kind"] for case in plan["cases"]} != {"place"}:
    raise ValueError("expected the same40 placement selection")
identity = plan["source_snapshot"]
if source.resolve() != Path(identity["path"]).resolve():
    raise ValueError("source differs from prepared source")
for ref in identity["files"]:
    path = Path(ref["path"]).resolve(strict=True)
    if not path.is_relative_to(source.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"registered source changed: {path}")
contract = plan["skill_chunk_contract"]
if (contract["controls_per_requested_chunk"] != 5 or contract["native_success_stops_chunk"] is not False
        or contract["private_joint_or_predicate_used_for_control"] is not False):
    raise ValueError("invalid full-block diagnostic contract")
PY

if [[ "${PLACE553_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  "$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards "$SHARDS" --states
  exit 0
fi
OUT="$BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$(dirname "$OUT")"
"$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --states \
  >"$BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$SOURCE"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --output "$OUT"
