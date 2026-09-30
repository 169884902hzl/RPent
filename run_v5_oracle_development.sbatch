#!/bin/bash
#SBATCH --job-name=libero-v5-original-dev
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=01:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:?independent source snapshot required}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
if [ -f "$ROOT/results/harness_v5/PAUSE_REQUESTED" ]; then
    echo "Yield requested; no new episode."
    exit 0
fi
if [ "${RUN_VOCAB_PROBE:-0}" = "1" ]; then
    "$ROOT/.venv/bin/python" -u "$SOURCE/v5_prompt_probe.py" \
        --manifest "$SOURCE/configs/v5_prompt_probe_original.json" \
        --output "$ROOT/results/harness_v5/vocabulary_probe_20260930/job${SLURM_JOB_ID}.jsonl"
fi
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
    --manifest "$SOURCE/configs/v5_original_development.json" \
    --provider oracle --choice-package "$PACKAGE" \
    --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
    --output-dir "$ROOT/results/harness_v5/original_development_20260929/job${SLURM_JOB_ID}"
