#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-expert-wrist103
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-1%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=06:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_wrist103_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config" PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT="$ROOT/results/harness_v5/original_gate_wrist103_200_20261001/job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$SOURCE/configs/v5_original_gate_proven36_20261001.json" \
 --provider oracle \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --shard-count 2 --shard-index "$SLURM_ARRAY_TASK_ID" \
 --pause-marker "$ROOT/results/harness_v5/original_gate_wrist103_200_20261001/PAUSE_REQUESTED_job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}" --output-dir "$OUT"
