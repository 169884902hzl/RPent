#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-runtime123
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format123_20261002"
UPSTREAM="$ROOT/results/harness_v5/format121_rerender_20261002/job2983"
OUT="$ROOT/results/harness_v5/format123_runtime_replay_20261002/job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec "$ROOT/.venv/bin/python" -u scripts/replay_measured_runtime123_20261002.py \
 --manifest "$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job2971/labeled_plus_validation6/manifest.json" \
 --cards "$UPSTREAM/cards/manifest.json" --measurements "$UPSTREAM/measurements/manifest.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --output "$OUT"
