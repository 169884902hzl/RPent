#!/usr/bin/env bash
# Owned public-parent original microwave development only; no node/dependency binding.
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-4%5
#SBATCH --nice=1000
#SBATCH --job-name=libero-microwave571
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

MICRO571_ROOT=/public/home/sunyihan/rpent_libero_eval
MICRO571_SOURCE=${MICRO571_SOURCE:?fixed SOURCE571 required}
MICRO571_MANIFEST=${MICRO571_MANIFEST:?registered original10 required}
MICRO571_MANIFEST_SHA=${MICRO571_MANIFEST_SHA:?manifest hash required}
MICRO571_ADAPTER=${MICRO571_ADAPTER:?owned public-parent selector required}
MICRO571_BASE=${MICRO571_BASE:?new independent output base required}
export PYTHONPATH="$MICRO571_SOURCE" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
export LIBERO_CONFIG_PATH="$MICRO571_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$MICRO571_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$MICRO571_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

"$MICRO571_ROOT/.venv/bin/python" - "$MICRO571_MANIFEST" "$MICRO571_MANIFEST_SHA" "$MICRO571_SOURCE" "$MICRO571_ADAPTER" "$MICRO571_BASE" <<'PY'
import hashlib,json,sys
from collections import Counter
from pathlib import Path
m,src,adapter,base=map(Path,(sys.argv[1],sys.argv[3],sys.argv[4],sys.argv[5]))
if not all(p.is_absolute() for p in (m,src,adapter,base)) or hashlib.sha256(m.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('absolute registered paths and exact manifest required')
plan=json.loads(m.read_text()); source=plan['source_snapshot']
if (plan['cohort']!='selection' or plan['qualification_authorized'] is not False or plan['new_training_rows']!=0
        or Counter(c['type'] for c in plan['cases'])!={'microwave_open':5,'microwave_close':5}
        or src!=Path(source['path']) or source['commit']!='5da67d19fe8dde8564e06c39266bb1fedc330d2a'
        or len(source['files'])!=24 or adapter!=Path(plan['adapter']['path'])):
    raise ValueError('original10 selection/source/adapter identity changed')
for ref in [*source['files'],source['archive'],plan['producer'],*plan['producer_dependencies']]:
    p=Path(ref['path'])
    if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError('explicit pinned file changed: '+str(p))
parent=json.loads(Path(plan['parent_manifest']['path']).read_text())
old=[c for c in parent['cases'] if c['type'] in ('microwave_open','microwave_close')]
for c,o in zip(plan['cases'],old,strict=True):
    if c['parent_case_name']!=o['name']:
        raise ValueError('registered ordering changed')
    for k in ('episode','setup','state_sha256','official_init_index','mode','type','bddl','init_file','subtask_prompt','original_instruction'):
        if c[k]!=o[k]:raise ValueError('registered original case changed: '+k)
condition=plan['conditions']['public_parent_current160']
if condition['executor']!='current' or condition['max_chunks']!=160 or condition['contact_approach']!='none' or condition['overrides']['dual_view_fusion_v1'] is not True:
    raise ValueError('current160 no-prehandle dual-view recipe changed')
contract=plan['skill_chunk_contract']
if contract['controls_per_requested_chunk']!=5 or contract['native_success_stops_chunk'] is not False or contract['private_joint_or_predicate_used_for_control'] is not False:
    raise ValueError('full5control contract changed')
PY

cd /tmp
if [[ "${MICRO571_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$MICRO571_ROOT/.venv/bin/python" "$MICRO571_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MICRO571_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 5 --states
fi
MICRO571_OUT="$MICRO571_BASE/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$MICRO571_BASE/job${SLURM_ARRAY_JOB_ID}"
"$MICRO571_ROOT/.venv/bin/python" "$MICRO571_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MICRO571_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 5 --states \
  > "$MICRO571_BASE/job${SLURM_ARRAY_JOB_ID}/preflight_part${SLURM_ARRAY_TASK_ID}.json"
cd "$MICRO571_SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
exec "$MICRO571_ROOT/.venv/bin/python" -u "$MICRO571_ADAPTER" \
  --manifest "$MICRO571_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 5 --output "$MICRO571_OUT"
