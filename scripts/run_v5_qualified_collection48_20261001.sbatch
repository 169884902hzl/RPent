#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-data-receipt48
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_collect_receipt48_20261001"
RESULTS="$ROOT/results/harness_v5/qualified_original_training48_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ -v SLURM_ARRAY_TASK_ID ]]; then
    PLAN="$SOURCE/configs/qualified_collection48_parts_20261001/part_${SLURM_ARRAY_TASK_ID}.json"
    OUT="$RESULTS/job${SLURM_ARRAY_JOB_ID}_task${SLURM_ARRAY_TASK_ID}"
else
    PLAN="$SOURCE/configs/qualified_collection48_smoke_20261001.json"
    OUT="$RESULTS/smoke_job${SLURM_JOB_ID}"
fi
"$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$PLAN" --provider oracle \
 --collection-config "$SOURCE/configs/qualified_collection48_config_20261001.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$RESULTS/PAUSE_REQUESTED_$(basename "$OUT")" --output-dir "$OUT"
if [[ ! -v SLURM_ARRAY_TASK_ID ]]; then
    "$ROOT/.venv/bin/python" "$SOURCE/scripts/check_original_collection_smoke_20261001.py" \
      --output "$OUT" --schema "$SOURCE/shared_v5r_schema.py"
fi
