#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-bind57-summary
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_bind57_20261001"
cd "$SOURCE"
export PYTHONPATH="$SOURCE"
exec "$ROOT/.venv/bin/python" "$SOURCE/scripts/summarize_v5_gate200_20261001.py" \
 --plan "$SOURCE/configs/v5_original_gate_proven36_20261001.json" \
 --array-job 2912 \
 --results-root "$ROOT/results/harness_v5/original_gate_bind57_200_20261001" \
 --output-dir "$ROOT/results/harness_v5/original_gate_bind57_200_20261001/summary_job${SLURM_JOB_ID}"
