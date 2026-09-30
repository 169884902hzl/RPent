#!/bin/bash
#SBATCH --job-name=libero-d2-a1n
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:?independent source snapshot required}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
exec "$ROOT/.venv/bin/python" -u "$SOURCE/original_api_batch.py" \
    --manifest "$SOURCE/configs/d2_development_40.json" \
    --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
    --output-dir "$ROOT/results/harness_v5/d2_a1n_20260930/job${SLURM_JOB_ID}"
