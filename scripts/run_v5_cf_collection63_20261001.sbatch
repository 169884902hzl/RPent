#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-cf-physical63
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-15%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=02:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_bind57_20261001"
PLAN="$ROOT/results/harness_v5/original_cf_physical63_20261001/preparation"
RESULTS="$ROOT/results/harness_v5/original_cf_physical63_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$PLAN/part_${SLURM_ARRAY_TASK_ID}.json" \
 --provider oracle --collection-config "$PLAN/collection_config.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$RESULTS/PAUSE_REQUESTED_job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}" \
 --output-dir "$RESULTS/job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}"
