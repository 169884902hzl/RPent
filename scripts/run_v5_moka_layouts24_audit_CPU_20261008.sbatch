#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --job-name=moka-layout-audit-CPU
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
MOKA_LAYOUT_AUDIT_ROOT=/public/home/sunyihan/rpent_libero_eval
MOKA_LAYOUT_AUDIT_SCRIPT=${MOKA_LAYOUT_AUDIT_SCRIPT:?pinned audit script required}
MOKA_LAYOUT_AUDIT_SCRIPT_SHA=${MOKA_LAYOUT_AUDIT_SCRIPT_SHA:?audit script SHA required}
MOKA_LAYOUT_AUDIT_REGISTRY=${MOKA_LAYOUT_AUDIT_REGISTRY:?pinned registry required}
MOKA_LAYOUT_AUDIT_REGISTRY_SHA=${MOKA_LAYOUT_AUDIT_REGISTRY_SHA:?registry SHA required}
MOKA_LAYOUT_AUDIT_MATERIALIZED=${MOKA_LAYOUT_AUDIT_MATERIALIZED:?pinned materialized manifest required}
MOKA_LAYOUT_AUDIT_MATERIALIZED_SHA=${MOKA_LAYOUT_AUDIT_MATERIALIZED_SHA:?materialized manifest SHA required}
MOKA_LAYOUT_AUDIT_OUTPUT=${MOKA_LAYOUT_AUDIT_OUTPUT:?fresh audit directory required}
export LIBERO_TYPE=standard LIBERO_CONFIG_PATH="$MOKA_LAYOUT_AUDIT_ROOT/runtime_config"
export PYTHONPATH="$MOKA_LAYOUT_AUDIT_ROOT" PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES="" MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$MOKA_LAYOUT_AUDIT_ROOT/.venv/bin/python" - "$MOKA_LAYOUT_AUDIT_SCRIPT" "$MOKA_LAYOUT_AUDIT_SCRIPT_SHA" <<'PY'
import hashlib,sys
from pathlib import Path
path=Path(sys.argv[1])
if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('Pinned audit script changed')
PY
cd /tmp
exec "$MOKA_LAYOUT_AUDIT_ROOT/.venv/bin/python" "$MOKA_LAYOUT_AUDIT_SCRIPT" \
  --registry "$MOKA_LAYOUT_AUDIT_REGISTRY" --registry-sha256 "$MOKA_LAYOUT_AUDIT_REGISTRY_SHA" \
  --materialized "$MOKA_LAYOUT_AUDIT_MATERIALIZED" --materialized-sha256 "$MOKA_LAYOUT_AUDIT_MATERIALIZED_SHA" \
  --output "$MOKA_LAYOUT_AUDIT_OUTPUT"
