#!/usr/bin/env bash
# Original development selection; no node/dependency binding, no qualification.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-4%5
#SBATCH --job-name=libero-drawer558-binding
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${DRAWER558_SOURCE:?pinned full-block source required}"
MANIFEST="${DRAWER558_MANIFEST:?binding5 manifest required}"
MANIFEST_SHA="${DRAWER558_MANIFEST_SHA:?manifest SHA required}"
SHARDS="${DRAWER558_SHARDS:-5}"
BASE="${DRAWER558_BASE:?independent output base required}"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$SOURCE" "$BASE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest, source, base = map(Path, (sys.argv[1], sys.argv[3], sys.argv[4]))
if not all(path.is_absolute() for path in (manifest, source, base)):
    raise ValueError("manifest/source/output require absolute paths")
if hashlib.sha256(manifest.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("registered paired manifest changed")
plan = json.loads(manifest.read_text())
if (plan.get("cohort") != "selection" or plan.get("qualification_authorized") is not False
        or plan.get("new_training_rows") != 0 or len(plan["cases"]) != 5):
    raise ValueError("only registered5 development cases, never confirmation/training")
identity = plan["source_snapshot"]
if source.resolve() != Path(identity["path"]).resolve():
    raise ValueError("source differs from prepared identity")
for ref in [*identity["files"], plan["producer"], *plan["producer_dependencies"]]:
    path = Path(ref["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"registered source/producer changed: {path}")
for ref in identity["files"]:
    if not Path(ref["path"]).resolve().is_relative_to(source.resolve()):
        raise ValueError("source file escapes pinned snapshot")
contract = plan["skill_chunk_contract"]
if (contract["controls_per_requested_chunk"] != 5 or contract["native_success_stops_chunk"] is not False
        or contract["private_joint_or_predicate_used_for_control"] is not False):
    raise ValueError("invalid complete control contract")
for case in plan["cases"]:
    if (case["episode"]["suite"] != "libero_90" or case["episode"]["task"] != 6
            or case["episode"]["seed"] not in range(10, 15) or case["kind"] != "articulate"
            or case["mode"] != "open" or case.get("setup")):
        raise ValueError("registered original initial case changed")
PY

if [[ "${DRAWER558_PREFLIGHT_ONLY:-0}" == 1 ]]; then
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
