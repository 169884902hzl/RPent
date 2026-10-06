#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=60G
#SBATCH --time=00:30:00
#SBATCH --job-name=libero-stove-public-crop-sam
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
STOVE_CROP_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE_CROP_MANIFEST="${STOVE_CROP_MANIFEST:?Register the explicit absolute manifest}"
STOVE_CROP_MANIFEST_SHA="${STOVE_CROP_MANIFEST_SHA:?Register manifest SHA256}"
STOVE_CROP_OUTPUT_ROOT="${STOVE_CROP_OUTPUT_ROOT:?Register independent output root}"
STOVE_CROP_SOURCE="$STOVE_CROP_ROOT/source_v5_stove555_20261006"
STOVE_CROP_PACKET="$STOVE_CROP_ROOT/results/harness_v5/stove555_live_CPU_20261006"
export PYTHONPATH="$STOVE_CROP_SOURCE" SAM3_CHECKPOINT_PATH="$STOVE_CROP_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /tmp
"$STOVE_CROP_ROOT/.venv/bin/python" "$STOVE_CROP_PACKET/offline_crop_sam.py" \
    --manifest "$STOVE_CROP_MANIFEST" --expected-manifest-sha256 "$STOVE_CROP_MANIFEST_SHA" \
    --preflight-only --output "$STOVE_CROP_OUTPUT_ROOT/preflight_job${SLURM_JOB_ID}.json"
"$STOVE_CROP_ROOT/.venv/bin/python" "$STOVE_CROP_PACKET/offline_crop_sam.py" \
    --manifest "$STOVE_CROP_MANIFEST" --expected-manifest-sha256 "$STOVE_CROP_MANIFEST_SHA" \
    --output "$STOVE_CROP_OUTPUT_ROOT/crop_job${SLURM_JOB_ID}"
