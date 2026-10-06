#!/usr/bin/env bash
# Original native drawer method selection; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=08:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-drawer559-native
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

DRAWER559_ROOT=/public/home/sunyihan/rpent_libero_eval
DRAWER559_SOURCE=${DRAWER559_SOURCE:?immutable SOURCE558 required}
DRAWER559_MANIFEST=${DRAWER559_MANIFEST:?registered selection200 required}
DRAWER559_MANIFEST_SHA=${DRAWER559_MANIFEST_SHA:?registered manifest SHA required}
DRAWER559_BASE=${DRAWER559_BASE:?independent output base required}
export PYTHONPATH="$DRAWER559_SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$DRAWER559_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$DRAWER559_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$DRAWER559_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

"$DRAWER559_ROOT/.venv/bin/python" - "$DRAWER559_MANIFEST" "$DRAWER559_MANIFEST_SHA" "$DRAWER559_SOURCE" "$DRAWER559_BASE" <<'PY'
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

manifest, source, base = map(Path, (sys.argv[1], sys.argv[3], sys.argv[4]))
if not all(p.is_absolute() for p in (manifest, source, base)):
    raise ValueError("Manifest/source/output require absolute paths")
if hashlib.sha256(manifest.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("Registered manifest changed")
plan = json.loads(manifest.read_text())
if (plan["cohort"] != "selection" or plan["qualification_authorized"] is not False
        or plan["new_training_rows"] != 0 or len(plan["cases"]) != 200):
    raise ValueError("Only registered200 selection cases authorized")
identity = plan["source_snapshot"]
if (source.resolve() != Path(identity["path"]).resolve()
        or identity["commit"] != "329e81961b100555078c33de8b872108d7b24b8a"
        or len(identity["files"]) != 24
        or identity["archive"]["sha256"] != "080d3ce9841e766a40530e87dae74d60aa2396fe42f1af35af5d87511ebd2e8c"):
    raise ValueError("Immutable SOURCE558 identity changed")
for ref in [*identity["files"], identity["archive"], plan["producer"], *plan["producer_dependencies"]]:
    p = Path(ref["path"])
    if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"Registered source/producer/reference changed: {p}")
if any(not Path(ref["path"]).resolve().is_relative_to(source.resolve()) for ref in identity["files"]):
    raise ValueError("Source file escapes immutable snapshot")
parent = json.loads(Path(plan["parent_manifest"]["path"]).read_text())
native = json.loads(Path(plan["native_recipe_reference"]["path"]).read_text())
if plan["conditions"] != {"native_original160": native["conditions"]["native_original160"]}:
    raise ValueError("Exact native SOURCE558 condition changed")
registered = {c["name"]: c for c in parent["cases"]}
if Counter(c["type"] for c in plan["cases"]) != {"drawer_open": 100, "drawer_close": 100}:
    raise ValueError("Open/close100 design changed")
if len({c["name"] for c in plan["cases"]}) != 200 or len({c["state_sha256"] for c in plan["cases"]}) != 200:
    raise ValueError("Distinct original cases changed")
for c in plan["cases"]:
    old = registered[c["parent_case_name"]]
    if c["condition"] != "native_original160" or c["subtask_prompt"] != old["original_instruction"]:
        raise ValueError("Literal registered original instruction changed")
    for key in ("episode", "setup", "state_sha256", "official_init_index", "type", "mode", "object_symbol", "object_category", "bddl", "init_file", "initial_state_repetition"):
        if c[key] != old[key]:
            raise ValueError(f"Registered original case changed: {key}")
contract = plan["skill_chunk_contract"]
if (contract["controls_per_requested_chunk"] != 5 or contract["native_success_stops_chunk"] is not False
        or contract["private_joint_or_predicate_used_for_control"] is not False):
    raise ValueError("Complete5controls contract changed")
PY

cd /tmp
if [[ "${DRAWER559_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$DRAWER559_ROOT/.venv/bin/python" "$DRAWER559_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$DRAWER559_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
DRAWER559_OUT="$DRAWER559_BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$DRAWER559_BASE/job${SLURM_ARRAY_JOB_ID}"
"$DRAWER559_ROOT/.venv/bin/python" "$DRAWER559_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$DRAWER559_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states \
  > "$DRAWER559_BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$DRAWER559_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$DRAWER559_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$DRAWER559_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$DRAWER559_OUT"
