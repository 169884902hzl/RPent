#!/bin/bash
#SBATCH --job-name=libero-v5-perception-probe
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_2e9fafa"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_perception_probe.py" \
    --image "$ROOT/results/harness_v5/development_smoke_20260929/job2560/agentview_high.png/00.png" \
    --output "$ROOT/results/harness_v5/perception_probe_20260929/job${SLURM_JOB_ID}.jsonl"
