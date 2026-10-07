#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-4%5
#SBATCH --nice=1000
#SBATCH --job-name=libero-temporal577-sampling
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
TEMPORAL577_ROOT=/public/home/sunyihan/rpent_libero_eval
TEMPORAL577_PACKET="${TEMPORAL577_PACKET:?Register owned temporal packet}"
TEMPORAL577_MANIFEST="${TEMPORAL577_MANIFEST:?Register sampling manifest}"
TEMPORAL577_MANIFEST_SHA="${TEMPORAL577_MANIFEST_SHA:?Register SHA256}"
TEMPORAL577_OUTPUT_ROOT="${TEMPORAL577_OUTPUT_ROOT:?Register independent output}"
export PYTHONPATH="$TEMPORAL577_ROOT/source_v5_stove555_20261006:$TEMPORAL577_ROOT/results/harness_v5/stove564_off_physical_development_CPU_20261006:$TEMPORAL577_ROOT/results/harness_v5/stove568_public_stop_selection_CPU_20261006:$TEMPORAL577_PACKET"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$TEMPORAL577_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$TEMPORAL577_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$TEMPORAL577_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
TEMPORAL577_RUN="$TEMPORAL577_OUTPUT_ROOT/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$TEMPORAL577_RUN"
cd /tmp
TEMPORAL577_ARGS=(--sampling-manifest "$TEMPORAL577_MANIFEST" --sampling-manifest-sha256 "$TEMPORAL577_MANIFEST_SHA" --shard-index "$SLURM_ARRAY_TASK_ID")
"$TEMPORAL577_ROOT/.venv/bin/python" "$TEMPORAL577_PACKET/sample_stove_multiframe.py" "${TEMPORAL577_ARGS[@]}" --preflight-only --preflight-report "$TEMPORAL577_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
if [[ "${TEMPORAL577_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
"$TEMPORAL577_ROOT/.venv/bin/python" -u "$TEMPORAL577_PACKET/sample_stove_multiframe.py" "${TEMPORAL577_ARGS[@]}" --output "$TEMPORAL577_RUN/part${SLURM_ARRAY_TASK_ID}"
