#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-pan553-cross-view
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
PAN553_ROOT=/public/home/sunyihan/rpent_libero_eval
PAN553_SOURCE=${PAN553_SOURCE:?absolute immutable source required}
PAN553_MANIFEST=${PAN553_MANIFEST:?absolute registered manifest required}
PAN553_MANIFEST_SHA=${PAN553_MANIFEST_SHA:?registered manifest SHA required}
PAN553_OUT="$PAN553_ROOT/results/harness_v5/pan553_cross_view_development10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$PAN553_OUT"
export PYTHONPATH="$PAN553_SOURCE" LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$PAN553_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$PAN553_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$PAN553_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# Validate the exact manifest and every declared path before loading services.
"$PAN553_ROOT/.venv/bin/python" - "$PAN553_MANIFEST" "$PAN553_MANIFEST_SHA" "$PAN553_SOURCE" <<'PY'
import hashlib
from pathlib import Path
import sys
manifest, source = Path(sys.argv[1]), Path(sys.argv[3])
if not manifest.is_absolute() or not source.is_absolute():
    raise ValueError("PAN553 manifest and source must be absolute")
if hashlib.sha256(manifest.resolve(strict=True).read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("PAN553 manifest changed")
for name in ("scripts/v5_probe_preflight.py", "scripts/probe_v5_grasp449_20261005.py",
             "robots/libero/v5_grasp_measurement.py"):
    (source / name).resolve(strict=True)
PY
cd /tmp
"$PAN553_ROOT/.venv/bin/python" "$PAN553_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$PAN553_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states \
  > "$PAN553_OUT/preflight.json"
cd "$PAN553_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$PAN553_ROOT/.venv/bin/python" -u "$PAN553_SOURCE/scripts/probe_v5_grasp449_20261005.py" \
  --manifest "$PAN553_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 \
  --output "$PAN553_OUT/probe"
