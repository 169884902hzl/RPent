#!/usr/bin/env bash
# Paired measured routes, using an explicit immutable code snapshot.
#SBATCH --job-name=rd-bounded-motion
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j-motion.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SOURCE:?absolute snapshot path required}
export SOURCE_COMMIT=${SOURCE_COMMIT:?snapshot commit required}
OUT=${OUT:-$ROOT/results/bounded_skills/motion_20261017/job$SLURM_JOB_ID}
[[ "$SOURCE" == /* && "$OUT" == /* ]]
test -f "$SOURCE/scripts/probe_bounded_motion.py"
test ! -e "$OUT"
mkdir -p "$(dirname "$OUT")"
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
cd "$SOURCE"
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_motion \
    --output "$OUT" --seed "${START_SEED:-0}" --count "${COUNT:-1}"
