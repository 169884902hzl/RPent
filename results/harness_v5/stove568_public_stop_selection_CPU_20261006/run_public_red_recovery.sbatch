#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-4%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-stove568-red-recovery
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
STOVE568_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE568_PACKET="${STOVE568_PACKET:?Register owned packet}"
STOVE568_MANIFEST="${STOVE568_MANIFEST:?Register public-observation manifest}"
STOVE568_MANIFEST_SHA="${STOVE568_MANIFEST_SHA:?Register SHA256}"
STOVE568_OUTPUT_ROOT="${STOVE568_OUTPUT_ROOT:?Register independent output root}"
export PYTHONPATH="$STOVE568_ROOT/source_v5_stove555_20261006:$STOVE568_ROOT/results/harness_v5/stove564_off_physical_development_CPU_20261006:$STOVE568_PACKET"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$STOVE568_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$STOVE568_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$STOVE568_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STOVE568_RUN="$STOVE568_OUTPUT_ROOT/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$STOVE568_RUN"
cd /tmp
STOVE568_ARGS=(--manifest "$STOVE568_MANIFEST" --expected-manifest-sha256 "$STOVE568_MANIFEST_SHA"
    --shard-index "$SLURM_ARRAY_TASK_ID")
"$STOVE568_ROOT/.venv/bin/python" -u "$STOVE568_PACKET/probe_public_red_recovery.py" \
    "${STOVE568_ARGS[@]}" --preflight-only --check-states --preflight-report "$STOVE568_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
if [[ "${STOVE568_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
"$STOVE568_ROOT/.venv/bin/python" -u "$STOVE568_PACKET/probe_public_red_recovery.py" \
    "${STOVE568_ARGS[@]}" --output "$STOVE568_RUN/part${SLURM_ARRAY_TASK_ID}"
