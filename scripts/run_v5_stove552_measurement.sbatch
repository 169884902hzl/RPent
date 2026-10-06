#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-stove552-measurement
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
STOVE552_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE552_SOURCE="${STOVE552_SOURCE:?Register an immutable source snapshot}"
STOVE552_MANIFEST="${STOVE552_MANIFEST:?Register the explicit absolute manifest}"
STOVE552_MANIFEST_SHA="${STOVE552_MANIFEST_SHA:?Register the manifest SHA256}"
STOVE552_OUTPUT_ROOT="${STOVE552_OUTPUT_ROOT:?Register an independent absolute output root}"
for STOVE552_PATH in "$STOVE552_SOURCE" "$STOVE552_MANIFEST" "$STOVE552_OUTPUT_ROOT"; do
    case "$STOVE552_PATH" in /*) ;; *) exit 2 ;; esac
done
export PYTHONPATH="$STOVE552_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$STOVE552_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$STOVE552_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$STOVE552_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STOVE552_RUN="$STOVE552_OUTPUT_ROOT/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$STOVE552_RUN"
cd /tmp
STOVE552_ARGS=(--source "$STOVE552_SOURCE" --manifest "$STOVE552_MANIFEST"
    --expected-manifest-sha256 "$STOVE552_MANIFEST_SHA" --shard-index "$SLURM_ARRAY_TASK_ID")
"$STOVE552_ROOT/.venv/bin/python" -u -m scripts.probe_v5_stove521_endpoint \
    "${STOVE552_ARGS[@]}" --preflight-only --check-states \
    --preflight-report "$STOVE552_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
"$STOVE552_ROOT/.venv/bin/python" -u -m scripts.probe_v5_stove521_endpoint \
    "${STOVE552_ARGS[@]}" --output "$STOVE552_RUN/part${SLURM_ARRAY_TASK_ID}"
