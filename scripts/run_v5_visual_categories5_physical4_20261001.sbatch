#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-category5
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=01:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_visual_categories5_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT="$ROOT/results/harness_v5/visual_categories5_physical4_20261001/job${SLURM_JOB_ID}"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$ROOT/configs/v5_visual_categories5_physical4_20261001.json" \
 --provider oracle \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --shard-count 1 --shard-index 0 --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
 --output-dir "$OUT"
