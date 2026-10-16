#!/usr/bin/env bash
# Single-source launcher for the 21705b8 feasibility probe.
# The startup probe uses this exact launcher and the same environment as the
# later array; it must create first_physical_request.json before expansion.
#SBATCH --job-name=rd-bounded-startup
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=02:00:00
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=$ROOT/source_bounded_21705b8_20261017
OUT=${OUT:?OUT must be supplied}
MANIFEST=${MANIFEST:?MANIFEST must be supplied}

export SOURCE_COMMIT=21705b8
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

cd "$SOURCE"
test -f "$MANIFEST"
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_feasibility \
  --manifest "$MANIFEST" \
  --arms oracle_k4 \
  --shard 0 --shards 220 \
  --output "$OUT" \
  --startup
