#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-prefix26
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_prefix30_20261001"
INDEX="$ROOT/configs/original_training1_prefix6_recovery2873_20261001.json"
OUT="$ROOT/results/harness_v5/original_training1_recovery26_509_20261001/packaged_after_task${RECOVERY_TRIGGER}"
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
PYTHON="$ROOT/.venv/bin/python"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" LIBERO_TYPE=standard LIBERO_CONFIG_PATH="$ROOT/runtime_config"
mkdir "$OUT"
exec > >(tee "$OUT/pipeline.log") 2>&1
set -x
"$PYTHON" "$SOURCE/scripts/audit_original_collection_20261001.py" --index "$INDEX" --output "$OUT/raw"
"$PYTHON" "$SOURCE/scripts/build_v5_original_goal_registry_20261001.py" --manifest "$OUT/raw/manifest.json" --episodes "$OUT/raw/episodes.json" --output "$OUT/original_target_registry.json"
"$PYTHON" "$SOURCE/scripts/relabel_original_prefix_20261001.py" --manifest "$OUT/raw/manifest.json" --choice-package "$PACKAGE" --output "$OUT/corrected"
"$PYTHON" "$SOURCE/scripts/rebuild_v5_runtime_sources_20261001.py" --manifest "$OUT/corrected/manifest.json" --output "$OUT/runtime_sources"
"$PYTHON" "$SOURCE/scripts/convert_v5_progress5_20261001.py" --manifest "$OUT/runtime_sources/manifest.json" --choice-package "$PACKAGE" --output "$OUT/progress5"
"$PYTHON" "$SOURCE/scripts/package_v5_labeled_prefix_20261001.py" --train-manifest "$OUT/progress5/manifest.json" --validation-manifest "$ROOT/results/harness_v5/original_validation6_20261001/audited6_sources/manifest.json" --target-registry "$OUT/original_target_registry.json" --output "$OUT/labeled_plus_validation6"
