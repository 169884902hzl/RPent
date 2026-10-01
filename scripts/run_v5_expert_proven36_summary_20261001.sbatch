#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-proven36-summary
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_proven36_20261001"
exec "$ROOT/.venv/bin/python" "$SOURCE/scripts/summarize_v5_gate200_20261001.py" \
 --plan "$SOURCE/configs/v5_original_gate_proven36_20261001.json" \
 --array-job "$EXPERT_ARRAY_JOB" \
 --results-root "$ROOT/results/harness_v5/original_gate_proven36_200_20261001" \
 --output-dir "$ROOT/results/harness_v5/original_gate_proven36_200_20261001/summary_job${EXPERT_ARRAY_JOB}"
