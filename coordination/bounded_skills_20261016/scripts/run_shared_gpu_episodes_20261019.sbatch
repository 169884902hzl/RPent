#!/usr/bin/env bash
#SBATCH --job-name=rd-bounded-shared-throughput
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
SOURCE=${SOURCE:?immutable SOURCE required}
MANIFEST=${MANIFEST:?absolute MANIFEST required}
LAUNCHER=${LAUNCHER:?absolute launcher required}
OUT=${OUT:-$ROOT/results/bounded_skills/shared_throughput_20261019/job${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID:-0}}
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=${LIBERO_TYPE:-standard} LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
cd "$SOURCE"
for path in "$MANIFEST" "$LAUNCHER"; do test "${path:0:1}" = / && test -f "$path"; done
test ! -e "$OUT"
ARGS=(--source "$SOURCE" --manifest "$MANIFEST" --domain "${DOMAIN:-original}" \
      --indices "${CASE_INDICES:?CASE_INDICES required}" --levels "${LEVELS:-4,8,12}")
if [[ -n "${STUDY_PLAN:-}" ]]; then ARGS+=(--study-plan "$STUDY_PLAN"); fi
"$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}" --preflight
if [[ "${STARTUP:-0}" == 1 ]]; then ARGS+=(--startup); fi
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}" --output "$OUT"
