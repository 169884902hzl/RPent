#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-recovery112-smoke
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=04:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_recovery112_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT="$ROOT/results/harness_v5/recovery112_smoke11_20261001/job${SLURM_JOB_ID}"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$SOURCE/configs/v5_recovery112_smoke11_20261001.json" \
 --provider oracle \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$ROOT/results/harness_v5/recovery112_smoke11_20261001/PAUSE_REQUESTED_job${SLURM_JOB_ID}" --output-dir "$OUT"
