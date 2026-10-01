#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-expert-bind4
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-1%2
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:-$ROOT/source_v5_compartment_binding4_20261001}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
OUT="$ROOT/results/harness_v5/original_gate_binding4_200_20261001/job${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID}}_task${SLURM_ARRAY_TASK_ID:-0}"
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
  --manifest "$ROOT/configs/v5_original_gate_binding4_20261001.json" \
  --provider oracle --choice-package "$PACKAGE" \
  --shard-count "${SHARD_COUNT:-2}" --shard-index "${SHARD_INDEX:-${SLURM_ARRAY_TASK_ID:-0}}" \
  --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
  --output-dir "$OUT"
