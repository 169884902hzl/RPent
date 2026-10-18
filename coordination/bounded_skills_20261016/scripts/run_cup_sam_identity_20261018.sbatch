#!/usr/bin/env bash
#SBATCH --job-name=rd-bounded-sam-identity
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=00:20:00
#SBATCH --nodelist=node02
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
export PYTHONPATH="$ROOT/source_bounded_3d71f44_20261018"
export SOURCE_COMMIT=3d71f446c846f0e7bc2b1ae2816f6aab6d3ed461
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
cd "$PYTHONPATH"
exec "$ROOT/.venv/bin/python" -u "$ROOT/results/bounded_skills/feasibility_20261017/preparation/cup8158_sam_identity_GPU_20261018.py"
