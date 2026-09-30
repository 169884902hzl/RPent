#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-original-gate
#SBATCH --partition=gpu
#SBATCH --nodelist=node01
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=08:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:?independent frozen gate snapshot required}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
    --manifest "$SOURCE/configs/v5_original_gate_200.json" \
    --provider oracle --choice-package "$PACKAGE" \
    --shard-count "${SHARD_COUNT:-1}" --shard-index "${SHARD_INDEX:-${SLURM_ARRAY_TASK_ID:-0}}" \
    --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
    --output-dir "$ROOT/results/harness_v5/original_gate_200_20260930/job${SLURM_JOB_ID}"
