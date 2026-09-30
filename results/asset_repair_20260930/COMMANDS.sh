#!/usr/bin/env bash
# Executed on the login node through ssh gpu5880-ts. No Slurm/GPU allocation.
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
PYTHON="$ROOT/.venv/bin/python"
DATASET=/public/home/sunyihan/liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602
INSTALL="$ROOT/.venv/lib/python3.10/site-packages/liberopro/liberopro"
OUTPUT="$ROOT/results/asset_repair_20260930"
REVISION=c86fc3b8293185a6f373677018ff3e37f8391602
export HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 LIBERO_TYPE=pro
export LIBEROPRO_DATASET_PATH="$DATASET"
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
ARGS=(--revision "$REVISION" --dataset "$DATASET" --install "$INSTALL" --output "$OUTPUT")

# First download used four workers; HTTP429 preserved, then resumed at one worker.
"$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" download "${ARGS[@]}" --max-workers 1

# Existing installation verification intentionally exits1 for empty arrays.
"$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" verify "${ARGS[@]}" \
  --report-name validation_before.json || test -f "$OUTPUT/validation_before.json"

"$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" compare "${ARGS[@]}"

# Check the HF copy without modifying the installed config or assets.
LIBERO_CONFIG_PATH="$OUTPUT/hf_config" \
  "$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" verify "${ARGS[@]}" \
  --report-name validation_hf.json

# install records squeue and refuses synchronization while any LIBERO job exists.
"$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" install "${ARGS[@]}"
"$PYTHON" -u "$ROOT/scripts/repair_liberopro_assets.py" verify "${ARGS[@]}" \
  --report-name validation_after.json

# Artifacts are immutable. This records the actual commands, not a rerun script
# for the same output directory; use a fresh output directory when reproducing.
