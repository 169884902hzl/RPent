#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-milk-replay75
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=03:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_milk_replay75_20261001"
PART="${MILK_REPLAY_PART:-smoke}"
RESULTS="$ROOT/results/harness_v5/milk_replay75_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT="$RESULTS/${PART}_job${SLURM_JOB_ID}"
"$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$SOURCE/configs/milk_replay75_20261001/${PART}.json" --provider oracle \
 --collection-config "$SOURCE/configs/milk_replay75_20261001/collection_config.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$RESULTS/PAUSE_REQUESTED_${PART}_job${SLURM_JOB_ID}" --output-dir "$OUT"
if [[ "$PART" == smoke ]]; then
 "$ROOT/.venv/bin/python" "$SOURCE/scripts/check_original_collection_smoke_20261001.py" \
  --output "$OUT" --schema "$SOURCE/shared_v5r_schema.py"
fi
