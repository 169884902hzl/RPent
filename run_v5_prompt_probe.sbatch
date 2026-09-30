#!/bin/bash
#SBATCH --job-name=libero-v5-vocab-probe
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=00:20:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:?independent source snapshot required}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_prompt_probe.py" \
    --manifest "$SOURCE/configs/v5_prompt_probe_original.json" \
    --output "$ROOT/results/harness_v5/vocabulary_probe_20260930/job${SLURM_JOB_ID}.jsonl"
