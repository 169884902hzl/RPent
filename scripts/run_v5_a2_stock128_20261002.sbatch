#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-a2-stock128
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
CONDITION="${LIBERO_A2_CONDITION:?N M or Mc}"
[[ "$CONDITION" == N || "$CONDITION" == M || "$CONDITION" == Mc ]]
OUT="$ROOT/results/harness_v5/a2_stock_development40_20261002/${CONDITION}_job${SLURM_JOB_ID}"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
ENDPOINT=$("$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import json
p=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/a2_stock_development40_20261002/service_job2986/ready.json')
d=json.loads(p.read_text())
assert d['ready'] and d['backend']=='vllm' and d['revision']=='e89b16ebf1988b3d6befa7de50abc2d76f26eb09'
print(d['base_url'])
PY
)
exec "$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider qwen27 --choice-endpoint "$ENDPOINT" \
 --manifest "$ROOT/results/harness_v5/a2_stock_development40_20261002/preparation128/cohorts/$CONDITION.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT"
