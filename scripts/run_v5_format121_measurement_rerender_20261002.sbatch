#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-format121-depth
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format121_20261002"
OUT="$ROOT/results/harness_v5/format121_rerender_20261002/job${SLURM_JOB_ID}"
MANIFEST="$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job2971/labeled_plus_validation6/manifest.json"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
sha256sum scripts/build_v5_category_cards118_20261002.py \
 scripts/rebuild_fixture_measurements121_20261002.py scripts/rerender_v5_format118_20261002.py \
 robots/libero/v5_cards.py robots/libero/v5_fixture_parts.py robots/libero/v5_state.py > "$OUT/source.sha256"
"$ROOT/.venv/bin/python" -u scripts/build_v5_category_cards118_20261002.py \
 --manifest "$MANIFEST" --include-registered-counterfactual --output "$OUT/cards"
"$ROOT/.venv/bin/python" -u scripts/rebuild_fixture_measurements121_20261002.py \
 --manifest "$MANIFEST" --output "$OUT/measurements"
exec "$ROOT/.venv/bin/python" -u scripts/rerender_v5_format118_20261002.py \
 --manifest "$MANIFEST" --cards "$OUT/cards/manifest.json" \
 --measurements "$OUT/measurements/manifest.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --output "$OUT/rendered"
