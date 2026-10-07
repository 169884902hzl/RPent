#!/usr/bin/env bash
# One original development decision; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=03:00:00
#SBATCH --job-name=libero-public-place-trace
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
TASK_ROOT=/public/home/sunyihan/rpent_libero_eval
TASK_SOURCE=${PLACE_TRACE_SOURCE:?immutable source required}
TASK_MANIFEST=${PLACE_TRACE_MANIFEST:?explicit single-case manifest required}
TASK_SHA=${PLACE_TRACE_MANIFEST_SHA:?manifest SHA required}
TASK_BASE=${PLACE_TRACE_BASE:?independent output base required}
export PYTHONPATH="$TASK_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$TASK_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$TASK_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$TASK_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$TASK_ROOT/.venv/bin/python" - "$TASK_MANIFEST" "$TASK_SHA" "$TASK_SOURCE" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest, source = Path(sys.argv[1]), Path(sys.argv[3])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == sys.argv[2]
plan = json.loads(manifest.read_text())
assert len(plan["cases"]) == 1 and plan["qualification_authorized"] is False
assert plan["new_training_rows"] == 0 and plan["permanent_training_exclusion"] is True
assert plan["source_snapshot"]["path"] == str(source)
for item in [*plan["source_snapshot"]["files"], plan["source_snapshot"]["archive"],
             plan["producer"], *plan["producer_dependencies"]]:
    assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
parent = json.loads(Path(plan["parent_manifest"]["path"]).read_text())
new = plan["cases"][0]
old = next(c for c in parent["cases"] if c["name"] == new["parent_case_name"])
for key in ("episode", "setup", "state_sha256", "subtask_prompt", "mode", "object_symbol", "bddl", "init_file"):
    assert new[key] == old[key], key
PY
cd /tmp
if [[ ${PLACE_TRACE_PREFLIGHT_ONLY:-0} == 1 ]]; then
  exec "$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --states
fi
TASK_OUT="$TASK_BASE/job${SLURM_JOB_ID}"
mkdir -p "$TASK_BASE"
"$TASK_ROOT/.venv/bin/python" "$TASK_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --states >"$TASK_BASE/preflight_job${SLURM_JOB_ID}.json"
cd "$TASK_SOURCE"
exec "$TASK_ROOT/.venv/bin/python" -u \
  "$TASK_SOURCE/coordination/drawer_public_identity_hold_CPU_20261008/probe_place_trace.py" \
  --manifest "$TASK_MANIFEST" --shard-index 0 --shards 1 --output "$TASK_OUT"
