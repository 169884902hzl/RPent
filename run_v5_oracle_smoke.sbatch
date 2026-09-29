#!/bin/bash
#SBATCH --job-name=libero-v5-oracle-smoke
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
OUT="$ROOT/results/harness_v5/oracle_smoke_20260929/job${SLURM_JOB_ID}"
mkdir -p "$(dirname "$OUT")"
if [ -f "$ROOT/results/harness_v5/PAUSE_REQUESTED" ]; then
    echo "GPU reservation yield requested before episode; no episode launched."
    exit 0
fi
exec "$ROOT/.venv/bin/python" -u "$SOURCE/harness_v5_eval.py" \
    --libero-type standard --suite libero_spatial --task 0 --seed 0 \
    --provider oracle --max-decisions 8 --max-chunks 40 \
    --choice-package "$PACKAGE" --output-dir "$OUT"
