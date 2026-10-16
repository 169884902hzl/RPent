#!/usr/bin/env bash
# Compatibility launcher for the bounded feasibility probe.
# The startup probe uses this exact launcher and the same environment as the
# later array; it must create first_physical_request.json before expansion.
#SBATCH --job-name=rd-bounded-feasibility
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SOURCE:-$ROOT/source_bounded_514b889_20261017}
MANIFEST=${MANIFEST:?MANIFEST must be supplied}
OUT=${OUT:-$ROOT/results/bounded_skills/feasibility_20261017/job${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID:-0}}

export SOURCE_COMMIT=${SOURCE_COMMIT:-514b889}
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

mkdir -p "$(dirname "$OUT")"
cd "$SOURCE"
test -f "$MANIFEST"
test -f "$SOURCE/scripts/v5_probe_preflight.py"
test ! -e "$OUT" || { echo "Output already exists: $OUT" >&2; exit 2; }
SHARD="${SLURM_ARRAY_TASK_ID:-${SHARD_ID:-0}}"
SHARD_COUNT_VALUE="${SHARD_COUNT:-220}"
"$ROOT/.venv/bin/python" -u -m scripts.v5_probe_preflight \
  --manifest "$MANIFEST" --shard-index "$SHARD" --shards "$SHARD_COUNT_VALUE" --states
EXTRA=()
if [[ "${STARTUP:-0}" == 1 ]]; then EXTRA+=(--startup); fi
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_feasibility \
  --manifest "$MANIFEST" \
  --arms "${PROBE_ARMS:-oracle_k4}" \
  --shard "$SHARD" --shards "$SHARD_COUNT_VALUE" \
  --output "$OUT" \
  "${EXTRA[@]}"
