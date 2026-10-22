#!/usr/bin/env bash
#SBATCH --job-name=rd-c3-s6-borrow-selected-grasp
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=100G
#SBATCH --time=02:00:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_selected_grasp_dda2c9f3_20261022"
PLAN="$ROOT/results/bounded_skills/execution_repairs_20261022/selected_grasp_dda2c9f3/manifest.json"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ARGS=(--source "$SOURCE" --manifest "$PLAN"
    --output "$ROOT/results/bounded_skills/execution_repairs_20261022/selected_grasp_dda2c9f3/probes"
    --common-starts "$ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/common_starts"
    --initial-mode restore --indices 29 27 23 1 6 15)
LAUNCHER="$SOURCE/coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py"
CUDA_VISIBLE_DEVICES='' "$ROOT/.venv/bin/python" "$LAUNCHER" "${ARGS[@]}" --preflight
exec "$ROOT/.venv/bin/python" -u "$LAUNCHER" "${ARGS[@]}"
