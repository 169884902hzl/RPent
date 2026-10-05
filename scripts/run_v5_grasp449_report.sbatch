#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=00:20:00
#SBATCH --job-name=libero-grasp449-report
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
BASE="$ROOT/results/harness_v5/grasp449_original_paired_20261005"
ARGS=()
for PART in {0..23}; do
  ARGS+=(--ledger "$BASE/full_job3436/part${PART}/episodes.jsonl")
done
OUT="$BASE/report_job${SLURM_JOB_ID}"
mkdir "$OUT"
export CUDA_VISIBLE_DEVICES=""
exec "$ROOT/.venv/bin/python" "$ROOT/runtime_launchers/summarize_v5_grasp449_20261005.py" \
  --manifest "$BASE/preparation_retry1/full.json" "${ARGS[@]}" --output "$OUT/report.json"
