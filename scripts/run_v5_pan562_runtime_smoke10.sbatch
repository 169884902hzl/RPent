#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-pan562-runtime
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
PAN562_ROOT=/public/home/sunyihan/rpent_libero_eval
PAN562_SOURCE=${PAN562_SOURCE:?immutable SOURCE562 required}
PAN562_MANIFEST=${PAN562_MANIFEST:?same10 visited selection required}
PAN562_MANIFEST_SHA=${PAN562_MANIFEST_SHA:?registered SHA required}
export PYTHONPATH="$PAN562_SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$PAN562_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$PAN562_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$PAN562_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PAN562_ROOT/.venv/bin/python" - "$PAN562_MANIFEST" "$PAN562_MANIFEST_SHA" "$PAN562_SOURCE" <<'PY'
import hashlib,json
from pathlib import Path
import sys
m,s=Path(sys.argv[1]),Path(sys.argv[3])
if not m.is_absolute() or not s.is_absolute() or hashlib.sha256(m.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('Absolute registered manifest/source required')
p=json.loads(m.read_text());identity=p['source_snapshot']
if (p['qualification_authorized'] is not False or p['new_training_rows']!=0 or len(p['cases'])!=10
        or identity['commit']!='e6f69a80ed2d26188a9b3233b72ad220d93cede8'
        or s.resolve()!=Path(identity['path']).resolve()):
    raise ValueError('Only same10 SOURCE562 development authorized')
for r in [*identity['files'],identity['archive'],p['producer'],*p['producer_dependencies'],p['parent_development_manifest']]:
    f=Path(r['path'])
    if not f.is_absolute() or hashlib.sha256(f.read_bytes()).hexdigest()!=r['sha256']:
        raise ValueError(f'Pinned reference changed: {f}')
for r in identity['files']:
    if not Path(r['path']).resolve().is_relative_to(s.resolve()):raise ValueError('Source file outside snapshot')
for c in p['conditions'].values():
    if not c['overrides']['grasp_category_profiles_v1'] or not c['overrides']['pan_coupled_lift_v1']:
        raise ValueError('Actual PAN runtime flags required')
PY
cd /tmp
if [[ "${PAN562_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$PAN562_ROOT/.venv/bin/python" "$PAN562_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$PAN562_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi
PAN562_OUT="$PAN562_ROOT/results/harness_v5/pan562_runtime_smoke10_CPU_20261006/physical_same10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$PAN562_OUT"
"$PAN562_ROOT/.venv/bin/python" "$PAN562_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$PAN562_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states > "$PAN562_OUT/preflight.json"
cd "$PAN562_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$PAN562_ROOT/.venv/bin/python" -u "$PAN562_SOURCE/scripts/probe_v5_grasp449_20261005.py" \
  --manifest "$PAN562_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$PAN562_OUT/probe"
