#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=60G
#SBATCH --time=00:30:00
#SBATCH --job-name=libero-stove-control-crop-sam
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
STOVE_CONTROL_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE_CONTROL_MANIFEST="${STOVE_CONTROL_MANIFEST:?Register the explicit absolute manifest}"
STOVE_CONTROL_MANIFEST_SHA="${STOVE_CONTROL_MANIFEST_SHA:?Register manifest SHA256}"
STOVE_CONTROL_OUTPUT_ROOT="${STOVE_CONTROL_OUTPUT_ROOT:?Register independent output root}"
STOVE_CONTROL_SOURCE="$STOVE_CONTROL_ROOT/source_v5_stove555_20261006"
STOVE_CONTROL_PACKET="$STOVE_CONTROL_ROOT/results/harness_v5/stove560_control_crop_CPU_20261006"
export PYTHONPATH="$STOVE_CONTROL_SOURCE" SAM3_CHECKPOINT_PATH="$STOVE_CONTROL_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /tmp
"$STOVE_CONTROL_ROOT/.venv/bin/python" "$STOVE_CONTROL_PACKET/offline_control_crop_sam.py" \
    --manifest "$STOVE_CONTROL_MANIFEST" --expected-manifest-sha256 "$STOVE_CONTROL_MANIFEST_SHA" \
    --preflight-only --output "$STOVE_CONTROL_OUTPUT_ROOT/preflight_job${SLURM_JOB_ID}.json"
if [[ "${STOVE_CONTROL_PREFLIGHT_ONLY:-0}" == 1 ]]; then
    exit 0
fi
"$STOVE_CONTROL_ROOT/.venv/bin/python" "$STOVE_CONTROL_PACKET/offline_control_crop_sam.py" \
    --manifest "$STOVE_CONTROL_MANIFEST" --expected-manifest-sha256 "$STOVE_CONTROL_MANIFEST_SHA" \
    --output "$STOVE_CONTROL_OUTPUT_ROOT/control_crop_job${SLURM_JOB_ID}"
