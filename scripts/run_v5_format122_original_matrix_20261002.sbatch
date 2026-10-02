#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-format122-original
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=05:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format122_20261002"
OUT="$ROOT/results/harness_v5/format122_original_matrix_20261002/job${SLURM_JOB_ID}"
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
sha256sum "$SOURCE/harness_v5_eval.py" "$SOURCE/robots/libero/v5_runtime.py" \
 "$SOURCE/robots/libero/v5_fixture_parts.py" "$SOURCE/robots/libero/v5_state.py" \
 "$SOURCE/configs/format122_parts.json" "$SOURCE/configs/format122_grasp.json" > "$OUT/source.sha256"
for CONDITION in parts; do
 "$ROOT/.venv/bin/python" -u v5_batch_eval.py \
  --manifest "$SOURCE/configs/format122_${CONDITION}.json" --provider oracle \
  --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
  --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/$CONDITION"
 [[ ! -e "$OUT/PAUSE_REQUESTED" ]] || break
done
