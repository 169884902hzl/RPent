#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-pan556-coupled-lift
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
PAN556_ROOT=/public/home/sunyihan/rpent_libero_eval
PAN556_SOURCE=${PAN556_SOURCE:?absolute immutable source required}
PAN556_MANIFEST=${PAN556_MANIFEST:?absolute registered manifest required}
PAN556_MANIFEST_SHA=${PAN556_MANIFEST_SHA:?registered manifest SHA required}
export PYTHONPATH="$PAN556_SOURCE" LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$PAN556_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$PAN556_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$PAN556_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PAN556_ROOT/.venv/bin/python" - "$PAN556_MANIFEST" "$PAN556_MANIFEST_SHA" "$PAN556_SOURCE" <<'PY'
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
if plan["qualification_authorized"] is not False or plan["new_training_rows"] != 0 or len(plan["cases"]) != 10:
    raise ValueError("only ten development selection cases authorized")
if source.resolve(strict=True) != Path(plan["source_snapshot"]["path"]).resolve(strict=True):
    raise ValueError("wrong source snapshot")
for ref in plan["source_snapshot"]["files"]:
    file = Path(ref["path"]).resolve(strict=True)
    if not file.is_relative_to(source.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError(f"source changed: {file}")
PY
cd /tmp
if [[ "${PAN556_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$PAN556_ROOT/.venv/bin/python" "$PAN556_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$PAN556_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
PAN556_OUT="$PAN556_ROOT/results/harness_v5/pan556_coupled_lift_development10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$PAN556_OUT"
"$PAN556_ROOT/.venv/bin/python" "$PAN556_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$PAN556_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states > "$PAN556_OUT/preflight.json"
cd "$PAN556_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$PAN556_ROOT/.venv/bin/python" -u "$PAN556_SOURCE/scripts/probe_v5_grasp449_20261005.py" \
  --manifest "$PAN556_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$PAN556_OUT/probe"
