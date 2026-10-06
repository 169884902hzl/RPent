#!/usr/bin/env bash
# Original development metrology only; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-drawer565-depth
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
TASK_ROOT=/public/home/sunyihan/rpent_libero_eval
TASK_SOURCE=${DRAWER565_SOURCE:?pinned source required}
TASK_MANIFEST=${DRAWER565_MANIFEST:?explicit manifest required}
TASK_SHA=${DRAWER565_MANIFEST_SHA:?registered manifest SHA required}
TASK_BASE=${DRAWER565_BASE:?independent output base required}
export PYTHONPATH="$TASK_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$TASK_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$TASK_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$TASK_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$TASK_ROOT/.venv/bin/python" - "$TASK_MANIFEST" "$TASK_SHA" "$TASK_SOURCE" "$TASK_BASE" <<'PY'
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

manifest, source, base = map(Path, (sys.argv[1], sys.argv[3], sys.argv[4]))
if not all(p.is_absolute() for p in (manifest, source, base)):
    raise ValueError("manifest/source/output must be absolute")
if hashlib.sha256(manifest.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("registered manifest changed")
plan = json.loads(manifest.read_text())
if (plan["cohort"] != "selection" or plan["qualification_authorized"] is not False
        or plan["new_training_rows"] != 0 or len(plan["cases"]) != 20):
    raise ValueError("expected development selection20, never confirmation or training")
identity = plan["source_snapshot"]
if source.resolve() != Path(identity["path"]).resolve():
    raise ValueError("source differs from prepared identity")
for item in [*identity["files"], identity["archive"], plan["producer"], *plan["producer_dependencies"]]:
    path = Path(item["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"registered file changed: {path}")
parent = json.loads(Path(plan["parent_manifest"]["path"]).read_text())
registered = {c["name"]: c for c in parent["cases"]}
if Counter(c["type"] for c in plan["cases"]) != {"drawer_open": 10, "drawer_close": 10}:
    raise ValueError("original open/close10 selection changed")
for case in plan["cases"]:
    old = registered[case["parent_case_name"]]
    for key in ("episode", "setup", "state_sha256", "subtask_prompt", "mode", "object_symbol", "bddl", "init_file"):
        if case[key] != old[key]:
            raise ValueError(f"registered original state changed: {key}")
if len(plan["conditions"]) != 1:
    raise ValueError("one registered development method required")
method, condition = next(iter(plan["conditions"].items()))
if method not in {"native_depth_v5_160", "native_public_stop_v6_160", "native_clearance_v8_160"}:
    raise ValueError("unregistered method")
if not all(condition["overrides"].get(flag) is True
           for flag in ("drawer_current_binding_v4", "drawer_bounds_depth_v5")):
    raise ValueError("required measured drawer binding/depth flags missing")
if method in {"native_public_stop_v6_160", "native_clearance_v8_160"} and condition["overrides"].get("drawer_public_stop_v6") is not True:
    raise ValueError("measured complete-endpoint stop missing")
if method == "native_clearance_v8_160" and (
        condition["overrides"].get("drawer_contact_clearance_v8") is not True
        or condition.get("private_fixture_sync") is not True):
    raise ValueError("measured release/clearance and read-only staged diagnostic missing")
PY
cd /tmp
if [[ "${DRAWER565_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$TASK_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
TASK_OUT="$TASK_BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$TASK_BASE/job${SLURM_ARRAY_JOB_ID}"
"$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$TASK_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states \
  >"$TASK_BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$TASK_SOURCE"
exec "$TASK_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$TASK_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$TASK_OUT"
