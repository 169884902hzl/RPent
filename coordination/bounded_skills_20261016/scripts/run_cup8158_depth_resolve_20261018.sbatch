#!/usr/bin/env bash
#SBATCH --job-name=rd-bounded-depth-resolve
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export PYTHONPATH=$ROOT/source_bounded_276456d_20261018
export LIBERO_CONFIG_PATH=$ROOT/runtime_config
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
cd "$PYTHONPATH"
exec "$ROOT/.venv/bin/python" -u "$ROOT/coordination/bounded_skills_20261016/scripts/cup8158_depth_resolve_GPU_20261018.py"
