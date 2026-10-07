#!/usr/bin/env bash
# Original already-visited development state; CPU preflight before services.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=03:00:00
#SBATCH --job-name=libero-drawer-endpoint-hold-v9
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
TASK_ROOT=/public/home/sunyihan/rpent_libero_eval
TASK_SOURCE=${DRAWER_V9_SOURCE:?immutable source required}
TASK_MANIFEST=${DRAWER_V9_MANIFEST:?explicit manifest required}
TASK_SHA=${DRAWER_V9_MANIFEST_SHA:?registered manifest SHA required}
TASK_BASE=${DRAWER_V9_BASE:?new output base required}
export PYTHONPATH="$TASK_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$TASK_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$TASK_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$TASK_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$TASK_ROOT/.venv/bin/python" - "$TASK_MANIFEST" "$TASK_SHA" "$TASK_SOURCE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
manifest, source = Path(sys.argv[1]), Path(sys.argv[3])
if hashlib.sha256(manifest.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("registered manifest changed")
plan = json.loads(manifest.read_text())
if (plan["version"] != "drawer-public-endpoint-hold/9-dev" or len(plan["cases"]) != 1
        or plan["qualification_authorized"] or plan["new_training_rows"] != 0
        or plan["source_snapshot"]["path"] != str(source)):
    raise ValueError("explicit development single-case contract changed")
for item in [*plan["source_snapshot"]["files"], plan["source_snapshot"]["archive"],
             plan["producer"], *plan["producer_dependencies"]]:
    if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError("registered source/input changed: " + item["path"])
parent = json.loads(Path(plan["parent_manifest"]["path"]).read_text())
old = next(c for c in parent["cases"] if c["name"] == plan["cases"][0]["parent_case_name"])
for key in ("episode", "setup", "state_sha256", "subtask_prompt", "mode", "object_symbol", "bddl", "init_file"):
    if plan["cases"][0][key] != old[key]:
        raise ValueError("original state/request changed: " + key)
PY
cd /tmp
if [[ "${DRAWER_V9_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --states
fi
TASK_OUT="$TASK_BASE/job${SLURM_JOB_ID}"
mkdir -p "$TASK_BASE"
"$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --states >"$TASK_BASE/preflight_job${SLURM_JOB_ID}.json"
cd "$TASK_SOURCE"
exec "$TASK_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --output "$TASK_OUT"
