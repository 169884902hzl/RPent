#!/bin/bash
#SBATCH --job-name=libero-pi05-realsteps
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=08:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=$ROOT/source_v5_termination_20261001
OUT=$ROOT/results/harness_v5/pi05_direct_realsteps_20261001/job${SLURM_JOB_ID}
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$OUT/identity"
sha256sum "$ROOT/scripts/pi05_direct_steps_20261001.py" "$ROOT/scripts/run_pi05_direct_steps_20261001.sbatch" "$SOURCE/rpent/robots/components/pi05_vla_server.py" "$SOURCE/robots/libero/tools.py" > "$OUT/identity/source.sha256"
scontrol show job "$SLURM_JOB_ID" > "$OUT/identity/job.txt"
exec "$ROOT/.venv/bin/python" -u "$ROOT/scripts/pi05_direct_steps_20261001.py" --source "$SOURCE" --output "$OUT/episodes"
