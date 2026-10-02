#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-expert-format128
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-1%2
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=05:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format128_20261002"
OUT="$ROOT/results/harness_v5/original_gate_format128_20261002/job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider oracle \
 --manifest "$ROOT/results/harness_v5/long35_resume128_20261002/preparation/expert200.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --shard-count 2 --shard-index "$SLURM_ARRAY_TASK_ID" \
 --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT"
