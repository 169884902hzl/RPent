#!/usr/bin/env bash
# Same original snapshot, explicit self and bounded VLA branches; no training.
#SBATCH --job-name=rd-bounded-forks
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=04:00:00
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j-forks.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SOURCE:?absolute snapshot path required}
MANIFEST=${MANIFEST:?absolute original manifest required}
export SOURCE_COMMIT=${SOURCE_COMMIT:?snapshot commit required}
OUT=${OUT:-$ROOT/results/bounded_skills/forks_20261017/job$SLURM_JOB_ID}
[[ "$SOURCE" == /* && "$MANIFEST" == /* && "$OUT" == /* ]]
test -f "$SOURCE/scripts/probe_bounded_forks.py"
test -f "$MANIFEST"
test ! -e "$OUT"
mkdir -p "$(dirname "$OUT")"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
cd "$SOURCE"
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_forks \
    --manifest "$MANIFEST" --output "$OUT" --count "${COUNT:-1}"
