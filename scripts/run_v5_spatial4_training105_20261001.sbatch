#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-spatial4-data105
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_wrist103_20261001"
RESULTS="$ROOT/results/harness_v5/spatial4_training105_20261001"
PART="${LIBERO_COLLECTION_PART:?set smoke or remaining}"
[[ "$PART" == smoke || "$PART" == remaining ]]
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT="$RESULTS/${PART}_job${SLURM_JOB_ID}"
"$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$RESULTS/preparation/${PART}.json" --provider oracle \
 --collection-config "$RESULTS/preparation/collection_config.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$RESULTS/PAUSE_REQUESTED_$(basename "$OUT")" --output-dir "$OUT"
if [[ "$PART" == smoke ]]; then
 "$ROOT/.venv/bin/python" "$SOURCE/scripts/check_original_collection_smoke_20261001.py" \
  --output "$OUT" --schema "$SOURCE/shared_v5r_schema.py"
fi
