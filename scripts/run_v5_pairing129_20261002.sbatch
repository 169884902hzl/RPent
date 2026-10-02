#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-pairing129-cpu
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_pairing129_20261002"
BASE="$ROOT/results/harness_v5/pairing129_delivery_20261002"
PART="${LIBERO_PAIRING_PART:?render delivery or expert_summary}"
OUT="$BASE/${PART}_job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
INPUT="$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job2971/labeled_plus_validation6/manifest.json"
if [[ "$PART" == render ]]; then
 exec "$ROOT/.venv/bin/python" -u scripts/rerender_v5_format118_20261002.py \
  --manifest "$INPUT" \
  --cards "$ROOT/results/harness_v5/format121_rerender_20261002/job2983/cards/manifest.json" \
  --measurements "$ROOT/results/harness_v5/format128_delivery_20261002/measure_job3002/manifest.json" \
  --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
  --output "$OUT"
elif [[ "$PART" == delivery ]]; then
 exec "$ROOT/.venv/bin/python" -u scripts/describe_format_delivery124_20261002.py \
  --rendered-manifest "$BASE/render_job${LIBERO_PAIRING_RENDER_JOB:?}/manifest.json" \
  --runtime-manifest "$ROOT/results/harness_v5/format128_delivery_20261002/runtime_job3004/manifest.json" \
  --source-manifest "$INPUT" --output "$OUT"
elif [[ "$PART" == expert_summary ]]; then
 exec "$ROOT/.venv/bin/python" -u scripts/summarize_v5_gate200_20261001.py \
  --plan "$ROOT/results/harness_v5/long35_resume128_20261002/preparation/expert200.json" \
  --array-job 3011 \
  --results-root "$ROOT/results/harness_v5/original_gate_format128_20261002" --output-dir "$OUT"
else
 exit 2
fi
