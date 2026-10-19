#!/usr/bin/env bash
#SBATCH --job-name=rd-bounded-shared-batch
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=20
#SBATCH --mem=140G
#SBATCH --time=18:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
test -f "${BATCH_PLAN:?absolute BATCH_PLAN required}"
test -f "${LAUNCHER:?absolute LAUNCHER required}"
RESULTS_ROOT=${RESULTS_ROOT:-$ROOT/results/bounded_skills/shared_remaining_20261019}
OUT=${OUT:-$RESULTS_ROOT/job${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}}
test ! -e "$OUT"
ARGS=(--batch-plan "$BATCH_PLAN")
"$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}" --preflight
if [[ "${STARTUP:-0}" == 1 ]]; then ARGS+=(--startup); fi
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}" --output "$OUT"
