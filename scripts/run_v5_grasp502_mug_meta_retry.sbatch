#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp502-meta-retry
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp502_mug_meta_retry_20261005"
BASE="$ROOT/results/harness_v5/grasp502_mug_meta_retry_20261005"
MANIFEST="$ROOT/results/harness_v5/grasp492_first4_confirmation_20261005/preparation/full.json"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
"$ROOT/.venv/bin/python" - "$MANIFEST" "$BASE/preparation/retry.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
manifest, registration = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
if hashlib.sha256(manifest.read_bytes()).hexdigest() != registration["original_manifest"]["sha256"]:
    raise RuntimeError("original confirmation registration changed")
client = Path(registration["patched_client"]["path"])
if hashlib.sha256(client.read_bytes()).hexdigest() != registration["patched_client"]["sha256"]:
    raise RuntimeError("registered strict-metadata client patch changed")
if registration["shard_index"] != 3 or registration["shards"] != 4:
    raise RuntimeError("retry is only the original zero-contact infrastructure shard")
PY
OUT="$BASE/retry_job${SLURM_JOB_ID}/part3"
"$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$MANIFEST" --shard-index 3 --shards 4 --output "$OUT"
