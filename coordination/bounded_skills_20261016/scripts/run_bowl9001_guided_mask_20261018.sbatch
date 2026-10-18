#!/usr/bin/env bash
#SBATCH --job-name=rd-bounded-bowl-sam
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
export PYTHONPATH="$ROOT/source_bounded_chunk_v3_panel_normal2_20261018_9f11e41"
export SOURCE_COMMIT=9f11e41
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
SCRIPT="$ROOT/coordination/bounded_skills_20261016/scripts/bowl9001_guided_mask_GPU_20261018.py"
cd "$PYTHONPATH"
"$ROOT/.venv/bin/python" "$SCRIPT" --prepare-only
exec "$ROOT/.venv/bin/python" -u "$SCRIPT"
