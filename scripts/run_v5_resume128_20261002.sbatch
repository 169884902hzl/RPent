#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-resume128
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=05:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format128_20261002"
PREP="$ROOT/results/harness_v5/long35_resume128_20261002/preparation"
PART="${LIBERO_RESUME_PART:?smoke or remaining}"
[[ "$PART" == smoke || "$PART" == remaining ]]
OUT="$ROOT/results/harness_v5/long35_resume128_20261002/${PART}_job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
EXTRA=()
if [[ "$PART" == remaining ]]; then
 EXTRA=(--collection-config "$PREP/collection_config.json")
fi
"$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider oracle \
 --manifest "$PREP/$PART.json" "${EXTRA[@]}" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT"
if [[ "$PART" == smoke ]]; then
 "$ROOT/.venv/bin/python" - "$OUT/episodes.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1])]
assert len(rows)==2
assert all(x['result']['correct_finish'] and x['result']['official_success'] and x['result']['status']=='completed' for x in rows)
print('ORIGINAL_BOOL_REPAIR_SMOKE_COMPLETE',2)
PY
fi
