#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-stove564-off20
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
STOVE564_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE564_SOURCE="${STOVE564_SOURCE:?Register immutable SOURCE555}"
STOVE564_PACKET="${STOVE564_PACKET:?Register owned off20 packet}"
STOVE564_MANIFEST="${STOVE564_MANIFEST:?Register implemented off20 manifest}"
STOVE564_MANIFEST_SHA="${STOVE564_MANIFEST_SHA:?Register implemented manifest SHA256}"
STOVE564_OUTPUT_ROOT="${STOVE564_OUTPUT_ROOT:?Register independent output root}"
for STOVE564_PATH in "$STOVE564_SOURCE" "$STOVE564_PACKET" "$STOVE564_MANIFEST" "$STOVE564_OUTPUT_ROOT"; do
    case "$STOVE564_PATH" in /*) ;; *) exit 2 ;; esac
done
export PYTHONPATH="$STOVE564_SOURCE:$STOVE564_PACKET" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$STOVE564_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$STOVE564_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$STOVE564_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
STOVE564_RUN="$STOVE564_OUTPUT_ROOT/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$STOVE564_RUN"
cd /tmp
STOVE564_ARGS=(--source "$STOVE564_SOURCE" --manifest "$STOVE564_MANIFEST"
    --expected-manifest-sha256 "$STOVE564_MANIFEST_SHA" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8)
"$STOVE564_ROOT/.venv/bin/python" -u "$STOVE564_PACKET/probe_off20.py" \
    "${STOVE564_ARGS[@]}" --preflight-only --check-states \
    --preflight-report "$STOVE564_RUN/preflight_part${SLURM_ARRAY_TASK_ID}.json"
if [[ "${STOVE564_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
"$STOVE564_ROOT/.venv/bin/python" -u "$STOVE564_PACKET/probe_off20.py" \
    "${STOVE564_ARGS[@]}" --output "$STOVE564_RUN/part${SLURM_ARRAY_TASK_ID}"
