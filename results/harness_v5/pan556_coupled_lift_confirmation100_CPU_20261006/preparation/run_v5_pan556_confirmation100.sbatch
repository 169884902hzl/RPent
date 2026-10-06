#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-pan556-confirm100
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
PANCONF_ROOT=/public/home/sunyihan/rpent_libero_eval
PANCONF_SOURCE=${PANCONF_SOURCE:?absolute immutable source required}
PANCONF_MANIFEST=${PANCONF_MANIFEST:?absolute registered manifest required}
PANCONF_MANIFEST_SHA=${PANCONF_MANIFEST_SHA:?registered manifest SHA required}
export PYTHONPATH="$PANCONF_SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$PANCONF_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$PANCONF_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$PANCONF_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PANCONF_ROOT/.venv/bin/python" - "$PANCONF_MANIFEST" "$PANCONF_MANIFEST_SHA" "$PANCONF_SOURCE" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
manifest, source = Path(sys.argv[1]), Path(sys.argv[3])
if not manifest.is_absolute() or not source.is_absolute():
    raise ValueError("source and manifest must be absolute")
if hashlib.sha256(manifest.resolve(strict=True).read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("registered manifest changed")
plan = json.loads(manifest.read_text())
if (plan["qualification_authorized"] is not False or plan["new_training_rows"] != 0
        or len(plan["cases"]) != 100 or plan["selection"] is not False):
    raise ValueError("only registered100 first confirmation trials authorized")
if (len({c["name"] for c in plan["cases"]}) != 100
        or len({c["registered_reset_id"] for c in plan["cases"]}) != 100
        or len({c["state_sha256"] for c in plan["cases"]}) != 99):
    raise ValueError("registered99-state100-reset design changed")
if source.resolve(strict=True) != Path(plan["source_snapshot"]["path"]).resolve(strict=True):
    raise ValueError("wrong source snapshot")
for condition in plan["conditions"].values():
    if condition.get("pan_coupled_lift_v1") is not True:
        raise ValueError("registered coupled lift measurement missing")
for ref in plan["source_snapshot"]["files"]:
    file = Path(ref["path"]).resolve(strict=True)
    if not file.is_relative_to(source.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"source changed: {file}")
PY
cd /tmp
if [[ "${PANCONF_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$PANCONF_ROOT/.venv/bin/python" "$PANCONF_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$PANCONF_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
PANCONF_OUT="$PANCONF_ROOT/results/harness_v5/pan556_coupled_lift_confirmation100/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$PANCONF_OUT"
"$PANCONF_ROOT/.venv/bin/python" "$PANCONF_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$PANCONF_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states > "$PANCONF_OUT/preflight.json"
cd "$PANCONF_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$PANCONF_ROOT/.venv/bin/python" -u "$PANCONF_SOURCE/scripts/probe_v5_grasp449_20261005.py" \
  --manifest "$PANCONF_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$PANCONF_OUT/probe"
