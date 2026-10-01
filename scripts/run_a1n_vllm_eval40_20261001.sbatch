#!/bin/bash
#SBATCH --job-name=libero-a1n-vllm40
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=14:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=$ROOT/source_v5_a1n_stock_20261001
SERVICE_OUT="$ROOT/results/harness_v5/a1n_vllm_development40_20261001/service_job${SERVICE_JOB:?}"
OUT="$ROOT/results/harness_v5/a1n_vllm_development40_20261001/eval_job${SLURM_JOB_ID}"
mkdir -p "$OUT"
trap 'touch "$SERVICE_OUT/EVALUATION_DONE"' EXIT
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export A1M_SERVICE_OUT="$SERVICE_OUT"
BASE_URL=$("$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import os,json,time
p=Path(os.environ['A1M_SERVICE_OUT'])/'ready.json';deadline=time.monotonic()+1000
while not p.exists():
 if time.monotonic()>deadline:raise RuntimeError(f'service not ready: {p}')
 time.sleep(2)
print(json.loads(p.read_text())['base_url'])
PY
)
sha256sum "$SOURCE/original_api_batch.py" "$ROOT/scripts/run_a1n_vllm_eval40_20261001.sbatch" "$ROOT/configs/a1n_vllm_development40_20261001/development40.json" > "$OUT/source.sha256"
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
cd "$SOURCE"
"$ROOT/.venv/bin/python" -u "$SOURCE/original_api_batch.py" \
 --manifest "$ROOT/configs/a1n_vllm_development40_20261001/development40.json" --base-url "$BASE_URL" \
 --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" --output-dir "$OUT/episodes"
touch "$SERVICE_OUT/EVALUATION_DONE"
