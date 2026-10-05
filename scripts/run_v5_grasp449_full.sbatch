#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-23%2
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=06:00:00
#SBATCH --job-name=libero-grasp449-full
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=$ROOT/source_v5_grasp449_20261005
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SOURCE"
exec "$ROOT/.venv/bin/python" -u scripts/probe_v5_grasp449_20261005.py \
  --manifest "$ROOT/results/harness_v5/grasp449_original_paired_20261005/preparation_retry1/full.json" \
  --shard-index "$SLURM_ARRAY_TASK_ID" --shards 24 \
  --output "$ROOT/results/harness_v5/grasp449_original_paired_20261005/full_job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
