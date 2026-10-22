#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-layout20-cpu
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --cpus-per-task=2
#SBATCH --mem=40G
#SBATCH --array=0-19%2
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export CUDA_VISIBLE_DEVICES=''
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" \
    "$ROOT/coordination/bounded_skills_20261016/scripts/prepare_train_layout_pilot_CPU_20261022.py" \
    --source "$LAYOUT_SOURCE" --registration "$LAYOUT_REGISTRATION" \
    --worker "$SLURM_ARRAY_TASK_ID"
