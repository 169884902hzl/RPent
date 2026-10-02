#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-format128-cpu
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format128_20261002"
UPSTREAM="$ROOT/results/harness_v5/format121_rerender_20261002/job2983"
BASE="$ROOT/results/harness_v5/format128_delivery_20261002"
PART="${LIBERO_FORMAT_PART:?measure render runtime or delivery}"
OUT="$BASE/${PART}_job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
INPUT="$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job2971/labeled_plus_validation6/manifest.json"
if [[ "$PART" == measure ]]; then
 exec "$ROOT/.venv/bin/python" -u scripts/rebuild_fixture_measurements121_20261002.py --manifest "$INPUT" --output "$OUT"
elif [[ "$PART" == render || "$PART" == runtime ]]; then
 SCRIPT=scripts/rerender_v5_format118_20261002.py
 [[ "$PART" != runtime ]] || SCRIPT=scripts/replay_measured_runtime123_20261002.py
 exec "$ROOT/.venv/bin/python" -u "$SCRIPT" --manifest "$INPUT" \
  --cards "$UPSTREAM/cards/manifest.json" --measurements "$BASE/measure_job${LIBERO_MEASURE_JOB:?}/manifest.json" \
  --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
  --output "$OUT"
elif [[ "$PART" == delivery ]]; then
 exec "$ROOT/.venv/bin/python" -u scripts/describe_format_delivery124_20261002.py \
  --rendered-manifest "$BASE/render_job${LIBERO_RENDER_JOB:?}/manifest.json" \
  --runtime-manifest "$BASE/runtime_job${LIBERO_RUNTIME_JOB:?}/manifest.json" \
  --source-manifest "$INPUT" --output "$OUT"
else
 exit 2
fi
