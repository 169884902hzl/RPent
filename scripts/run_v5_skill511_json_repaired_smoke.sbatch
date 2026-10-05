#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-4%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-skill511-smoke
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_skill511_json_repaired_20261005"
BASE="$ROOT/results/harness_v5/skill511_json_repaired_smoke_20261005"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
case "$SLURM_ARRAY_TASK_ID" in
  0|1|2)
    MANIFEST="$BASE/preparation/fixtures_smoke.json"
    MANIFEST_SHA=4b41dd0ce72b7694a20d0e1c95f299ac1caab77ae5f798ae0e3893cc11c65c37
    SKILL_INDEX="$SLURM_ARRAY_TASK_ID"; SKILL_SHARDS=3 ;;
  3)
    MANIFEST="$BASE/preparation/place_smoke.json"
    MANIFEST_SHA=37d3eac254090f553b9854846b922b359e3f83118626e3c0d18fcb2561c672c1
    SKILL_INDEX=0; SKILL_SHARDS=1 ;;
  4)
    MANIFEST="$BASE/preparation/grasp_subtask_smoke.json"
    MANIFEST_SHA=4ec7550ae488c9a77d3cf52694a8ad4ce49a8624478fc14db3b583e145163b02
    SKILL_INDEX=0; SKILL_SHARDS=1 ;;
esac
"$ROOT/.venv/bin/python" - "$MANIFEST" "$MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise RuntimeError("registered development smoke changed")
PY
OUT="$BASE/smoke_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
"$ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$MANIFEST" --shard-index "$SKILL_INDEX" --shards "$SKILL_SHARDS" --output "$OUT"
