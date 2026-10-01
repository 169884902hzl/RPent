#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-a4-diag-summary
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_a4_summary39_20261001"
exec "$ROOT/.venv/bin/python" "$SOURCE/scripts/summarize_v5_timing40_20261001.py" \
 --manifest "$SOURCE/configs/v5_a4_jev_d2_diagnostic40_summary_20261001.json" \
 --results "$ROOT/results/harness_v5/a4_jev_d2_diagnostic40_20261001/job${A4_DIAGNOSTIC_JOB:?}"
