#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-mask-probe
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:15:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_compartment_binding4_20261001"
OUT="$ROOT/results/harness_v5/perception_mask_probe_20261001/job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" -u "$ROOT/scripts/probe_v5_category_masks_20261001.py" \
  --manifest "$ROOT/configs/v5_perception_mask_probe_20261001.json" \
  --checkpoint "$ROOT/assets/sam3/sam3.pt" --output "$OUT"
