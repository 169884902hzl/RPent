#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-union91
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_prefix30_20261001"
STATS="$ROOT/source_v5_package_stats40_20261001"
AUDITOR="$ROOT/source_v5_milk_replay75_20261001"
INDEX="$ROOT/results/harness_v5/qualified_original_training48_20261001/cumulative_index91_cf16_complete.json"
OUT="$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job${SLURM_JOB_ID}"
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
PYTHON="$ROOT/.venv/bin/python"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" LIBERO_TYPE=standard LIBERO_CONFIG_PATH="$ROOT/runtime_config"
mkdir "$OUT"
exec > >(tee "$OUT/pipeline.log") 2>&1
set -x
"$PYTHON" "$AUDITOR/scripts/audit_original_collection_20261001.py" --index "$INDEX" --output "$OUT/raw"
"$PYTHON" "$SOURCE/scripts/build_v5_original_goal_registry_20261001.py" --manifest "$OUT/raw/manifest.json" --episodes "$OUT/raw/episodes.json" --output "$OUT/original_target_registry.json"
"$PYTHON" "$SOURCE/scripts/relabel_original_prefix_20261001.py" --manifest "$OUT/raw/manifest.json" --choice-package "$PACKAGE" --output "$OUT/corrected"
"$PYTHON" "$SOURCE/scripts/rebuild_v5_runtime_sources_20261001.py" --manifest "$OUT/corrected/manifest.json" --output "$OUT/runtime_sources"
"$PYTHON" "$SOURCE/scripts/convert_v5_progress5_20261001.py" --manifest "$OUT/runtime_sources/manifest.json" --choice-package "$PACKAGE" --output "$OUT/progress5"
"$PYTHON" "$STATS/scripts/package_v5_labeled_prefix_20261001.py" --train-manifest "$OUT/progress5/manifest.json" --validation-manifest "$ROOT/results/harness_v5/original_validation6_20261001/audited6_sources/manifest.json" --target-registry "$OUT/original_target_registry.json" --output "$OUT/labeled_plus_validation6"

for PRIOR in 2923 2930 2920 2934 2938; do
 "$PYTHON" "$ROOT/runtime_launchers/compare_v5_prefix72_20261001.py" \
  --old "$ROOT/results/harness_v5/qualified_original_training48_20261001/packaged_job${PRIOR}/labeled_plus_validation6/manifest.json" \
  --new "$OUT/labeled_plus_validation6/manifest.json" --output "$OUT/actual_delta_job${PRIOR}.json"
done
