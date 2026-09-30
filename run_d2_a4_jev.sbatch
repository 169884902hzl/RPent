#!/usr/bin/env bash
#SBATCH --job-name=libero-d2-a4-jev
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="${SOURCE:-$ROOT/source_v5_expert_bindfix2_20260930}"
OUTPUT="$ROOT/results/harness_v5/d2_a4_jev_20260930/job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBEROPRO_DATASET_PATH=/public/home/sunyihan/liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
exec "$ROOT/.venv/bin/python" -u "$SOURCE/v5_batch_eval.py" \
  --manifest "$SOURCE/configs/d2_development_40.json" \
  --provider jev --choice-package "$PACKAGE" \
  --choice-endpoint "${JEV_ENDPOINT:-http://node01:18582}" \
  --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
  --output-dir "$OUTPUT"
