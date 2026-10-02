#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-format124-delivery
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format124_20261002"
OUT="$ROOT/results/harness_v5/format124_delivery_20261002/job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" -u scripts/describe_format_delivery124_20261002.py \
 --rendered-manifest "$ROOT/results/harness_v5/format122_rerender_20261002/job2985/manifest.json" \
 --runtime-manifest "$ROOT/results/harness_v5/format123_runtime_replay_20261002/job2990/manifest.json" \
 --source-manifest "$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job2971/labeled_plus_validation6/manifest.json" \
 --output "$OUT"
