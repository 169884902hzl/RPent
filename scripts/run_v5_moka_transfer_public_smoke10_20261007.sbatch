#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-moka-transfer
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
MOKA_TRANSFER_ROOT=/public/home/sunyihan/rpent_libero_eval
MOKA_TRANSFER_SOURCE=${MOKA_TRANSFER_SOURCE:?immutable source required}
MOKA_TRANSFER_MANIFEST=${MOKA_TRANSFER_MANIFEST:?visited-state smoke manifest required}
MOKA_TRANSFER_MANIFEST_SHA=${MOKA_TRANSFER_MANIFEST_SHA:?registered manifest SHA required}
export PYTHONPATH="$MOKA_TRANSFER_SOURCE:$MOKA_TRANSFER_ROOT" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
MOKA_TRANSFER_PREP=$(dirname "$MOKA_TRANSFER_MANIFEST")
export PYTHONPATH="$MOKA_TRANSFER_PREP:$MOKA_TRANSFER_SOURCE:$MOKA_TRANSFER_ROOT"
export LIBERO_CONFIG_PATH="$MOKA_TRANSFER_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$MOKA_TRANSFER_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$MOKA_TRANSFER_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$MOKA_TRANSFER_MANIFEST" "$MOKA_TRANSFER_MANIFEST_SHA" "$MOKA_TRANSFER_SOURCE" <<'PY'
import hashlib,json
from pathlib import Path
import sys
m,s=Path(sys.argv[1]),Path(sys.argv[3])
if not m.is_absolute() or not s.is_absolute() or hashlib.sha256(m.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('Absolute pinned manifest/source required')
p=json.loads(m.read_text()); identity=p['source_snapshot']
if (p['qualification_authorized'] is not False or p['new_training_rows']!=0
        or p['selection']['analysis_role']!='development_visited_state_smoke'
        or len(p['cases'])!=10 or s.resolve()!=Path(identity['path']).resolve()):
    raise ValueError('Only the registered ten visited development states are authorized')
for r in [*identity['files'],identity['archive'],p['producer'],*p['producer_dependencies']]:
    f=Path(r['path'])
    if not f.is_absolute() or hashlib.sha256(f.read_bytes()).hexdigest()!=r['sha256']:
        raise ValueError(f'Pinned reference changed: {f}')
supplement=m.parent / 'typed_choice_eval.py'
if not supplement.is_file():
    raise ValueError('registered typed_choice_eval.py supplement missing')
PY
cd /tmp
if [[ "${MOKA_TRANSFER_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$MOKA_TRANSFER_ROOT/.venv/bin/python" "$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
MOKA_TRANSFER_BASE="$MOKA_TRANSFER_ROOT/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007"
MOKA_TRANSFER_OUT="$MOKA_TRANSFER_BASE/smoke10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$MOKA_TRANSFER_OUT"
"$MOKA_TRANSFER_ROOT/.venv/bin/python" "$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states > "$MOKA_TRANSFER_OUT/preflight.json"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$MOKA_TRANSFER_ROOT/.venv/bin/python" -u "$MOKA_TRANSFER_ROOT/scripts/probe_v5_moka_transfer_public_20261007.py" \
  --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$MOKA_TRANSFER_OUT/probe"
