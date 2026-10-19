#!/usr/bin/env bash
# One owned service pair per D2 evaluation shard; no training.
#SBATCH --job-name=rd-bounded-hybrid-d2
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=500
#SBATCH --nodelist=node02
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SOURCE:?SOURCE must name the immutable source snapshot}
MANIFEST=${MANIFEST:?MANIFEST must name the pinned D2-only plan}
OUT=${OUT:-$ROOT/results/bounded_skills/hybrid_d2_20261019/job${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID:-0}}
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
test "${SOURCE:0:1}" = / && test "${MANIFEST:0:1}" = /
test -f "$MANIFEST" && test -f "$SOURCE/scripts/probe_bounded_hybrid_d2.py"
test ! -e "$OUT"
mkdir -p "$(dirname "$OUT")"
cd "$SOURCE"
EXTRA=()
if [[ "${STARTUP:-0}" == 1 ]]; then EXTRA+=(--startup); fi
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_hybrid_d2 \
  --manifest "$MANIFEST" --index "${SLURM_ARRAY_TASK_ID:-0}" --output "$OUT" "${EXTRA[@]}"
