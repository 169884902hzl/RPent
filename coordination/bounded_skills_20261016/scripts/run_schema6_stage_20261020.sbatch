#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-schema6
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
: "${SCHEMA6_SOURCE:?absolute snapshot required}"
: "${SCHEMA6_MANIFEST:?absolute manifest required}"
: "${SCHEMA6_OUTPUT:?case-resumable output required}"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
if [[ "${SCHEMA6_N1:-0}" == 1 ]]; then
    LAUNCHER=${SCHEMA6_LAUNCHER:-$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py}
else
    LAUNCHER=${SCHEMA6_LAUNCHER:-$SCHEMA6_SOURCE/coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py}
fi
ARGS=(--source "$SCHEMA6_SOURCE" --manifest "$SCHEMA6_MANIFEST" --output "$SCHEMA6_OUTPUT")
if [[ "${SCHEMA6_N1:-0}" != 1 ]]; then
    ARGS+=(--episode-concurrency "${SCHEMA6_CONCURRENCY:-8}")
fi
"$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
if [[ "${SCHEMA6_STARTUP_ONLY:-0}" == 1 ]]; then ARGS+=(--startup-only); fi
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
