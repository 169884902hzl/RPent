#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --job-name=moka-layouts24-CPU
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
MOKA_LAYOUT_ROOT=/public/home/sunyihan/rpent_libero_eval
MOKA_LAYOUT_SCRIPT=${MOKA_LAYOUT_SCRIPT:?pinned materializer required}
MOKA_LAYOUT_SCRIPT_SHA=${MOKA_LAYOUT_SCRIPT_SHA:?materializer SHA required}
MOKA_LAYOUT_REGISTRY=${MOKA_LAYOUT_REGISTRY:?pinned layout registry required}
MOKA_LAYOUT_REGISTRY_SHA=${MOKA_LAYOUT_REGISTRY_SHA:?registry SHA required}
MOKA_LAYOUT_OUTPUT=${MOKA_LAYOUT_OUTPUT:?fresh preparation output required}
MOKA_LAYOUT_RESET_SOURCE=${MOKA_LAYOUT_RESET_SOURCE:?pinned deterministic-reset adapter required}
MOKA_LAYOUT_RESET_SOURCE_SHA=${MOKA_LAYOUT_RESET_SOURCE_SHA:?reset adapter SHA required}
export PYTHONPATH="$MOKA_LAYOUT_ROOT" LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$MOKA_LAYOUT_ROOT/runtime_config"
export CUDA_VISIBLE_DEVICES="" MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
"$MOKA_LAYOUT_ROOT/.venv/bin/python" - "$MOKA_LAYOUT_SCRIPT" "$MOKA_LAYOUT_SCRIPT_SHA" <<'PY'
import hashlib,sys
from pathlib import Path
path=Path(sys.argv[1])
if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('Pinned materializer changed')
PY
cd /tmp
exec "$MOKA_LAYOUT_ROOT/.venv/bin/python" "$MOKA_LAYOUT_SCRIPT" \
  --registry "$MOKA_LAYOUT_REGISTRY" --registry-sha256 "$MOKA_LAYOUT_REGISTRY_SHA" \
  --reset-seed-source "$MOKA_LAYOUT_RESET_SOURCE" --reset-seed-source-sha256 "$MOKA_LAYOUT_RESET_SOURCE_SHA" \
  --output "$MOKA_LAYOUT_OUTPUT"
