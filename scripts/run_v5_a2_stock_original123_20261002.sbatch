#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-stock123-original
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=02:00:00
#SBATCH --nice=15000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_format123_20261002"
OUT="$ROOT/results/harness_v5/a2_stock_development40_20261002/original_probe_job${SLURM_JOB_ID}"
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
sha256sum harness_v5_eval.py typed_choice_eval.py v5_qwen27_guided_choice.py \
 robots/libero/v5_state.py configs/stock_original_probe123.json configs/long5_original123.json > "$OUT/source.sha256"
ENDPOINT=$("$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import json
p=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5/a2_stock_development40_20261002/service_job2986/ready.json')
data=json.loads(p.read_text())
assert data['ready'] and data['backend']=='vllm' and data['revision']=='e89b16ebf1988b3d6befa7de50abc2d76f26eb09'
print(data['base_url'])
PY
)
"$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider qwen27 --choice-endpoint "$ENDPOINT" \
 --manifest "$SOURCE/configs/stock_original_probe123.json" \
 --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
 --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/qwen27"
if [[ ! -e "$OUT/PAUSE_REQUESTED" ]]; then
 "$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider oracle \
  --manifest "$SOURCE/configs/long5_original123.json" \
  --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a \
  --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/long5"
fi
