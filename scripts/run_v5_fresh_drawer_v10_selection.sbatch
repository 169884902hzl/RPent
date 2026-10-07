#!/usr/bin/env bash
# Original same40 choice states, no node/dependency binding or qualification.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=12:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-place-fresh579
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${FRESH579_SOURCE:?fixed source required}"
MANIFEST="${FRESH579_MANIFEST:?same40 manifest required}"
MANIFEST_SHA="${FRESH579_MANIFEST_SHA:?manifest SHA required}"
BASE="${FRESH579_BASE:?independent output base required}"
SHARDS=8
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" "$SOURCE" <<'PY'
import hashlib,json,sys
from pathlib import Path
m,s=Path(sys.argv[1]),Path(sys.argv[3])
assert m.is_absolute() and s.is_absolute()
assert hashlib.sha256(m.read_bytes()).hexdigest()==sys.argv[2]
a=json.loads(m.read_text())
assert a['cohort']=='selection' and a['qualification_authorized'] is False and a['new_training_rows']==0
assert len(a['cases'])==40 and {c['kind'] for c in a['cases']}=={'place'}
identity=a['source_snapshot'];assert s.resolve()==Path(identity['path']).resolve()
for x in identity['files']:
 p=Path(x['path']).resolve(strict=True)
 assert p.is_relative_to(s.resolve()) and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
x=identity['archive'];assert hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256']
assert a['fresh_drawer_contract']['cabinet_fragment_alias_default'] is False
assert a['fresh_drawer_contract']['footprint_thresholds_changed'] is False
c=a['skill_chunk_contract'];assert c['controls_per_requested_chunk']==5 and c['native_success_stops_chunk'] is False
assert c['private_joint_or_predicate_used_for_control'] is False
PY
if [[ "${FRESH579_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  "$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards "$SHARDS" --states
  exit 0
fi
OUT="$BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$(dirname "$OUT")"
"$ROOT/.venv/bin/python" "$SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --states \
  >"$BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$SOURCE"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards "$SHARDS" --output "$OUT"
