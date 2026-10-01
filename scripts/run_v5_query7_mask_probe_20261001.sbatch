#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-query7-probe
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:15:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_visual_binding6_20261001"
OUT="$ROOT/results/harness_v5/query7_mask_probe_20261001/job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
for SCENE in stove packages; do
  "$ROOT/.venv/bin/python" -u "$ROOT/scripts/probe_v5_category_masks_20261001.py" \
    --manifest "$ROOT/configs/v5_query7_${SCENE}_20261001.json" \
    --checkpoint "$ROOT/assets/sam3/sam3.pt" --output "$OUT/$SCENE"
done
