#!/bin/bash
#SBATCH --job-name=libero-d2-a1n-context
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
RDROOT=/public/home/sunyihan/rd_instruction_20260923
SOURCE="${SOURCE:?independent RPent source snapshot required}"
OUTPUT="$ROOT/results/harness_v5/d2_a1n_context_20260930/job${SLURM_JOB_ID}"
RUNTIME="$OUTPUT/runtime"
mkdir -p "$RUNTIME"
cp "$RDROOT/m1_b2_20260929/m2_api.py" "$RDROOT/m1_b2_20260929/m2_launch.py" "$RUNTIME/"
sha256sum "$RUNTIME/m2_api.py" "$RUNTIME/m2_launch.py" > "$OUTPUT/service_source.sha256"
VENV="$RDROOT/v5_qwen36_api/.sglang-venv"
set +u
source /public/apps/anaconda3/etc/profile.d/conda.sh
conda activate "$RDROOT/v5_qwen36_api/cuda128"
set -u
export CUDA_HOME="$RDROOT/v5_qwen36_api/cuda128"
export PATH="$VENV/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$RUNTIME:$SOURCE"
export M2_BACKEND_KIND=sglang M2_BACKEND_URL=http://127.0.0.1:18037
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$RUNTIME"
"$VENV/bin/python" -u "$RUNTIME/m2_launch.py" \
    --model-path "$RDROOT/v5_models/Qwen3.6-27B-FP8" \
    --served-model-name Qwen3.6-27B-FP8 --host 127.0.0.1 --port 18037 \
    --tp-size 1 --context-length 32768 --mem-fraction-static 0.60 \
    --max-running-requests 1 --max-total-tokens 32768 --disable-cuda-graph \
    --attention-backend triton --sampling-backend pytorch \
    --disable-radix-cache --enable-nan-detection \
    --tool-call-parser qwen3_coder --reasoning-parser qwen3 > "$OUTPUT/sglang.log" 2>&1 &
BACKEND_PID=$!
"$VENV/bin/python" -m uvicorn m2_api:app --host 127.0.0.1 --port 18361 --no-access-log > "$OUTPUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$BACKEND_PID" "$GATEWAY_PID" 2>/dev/null || true' EXIT
"$ROOT/.venv/bin/python" - "$OUTPUT/health.json" <<'PY'
import json
import sys
import time
import urllib.request
deadline = time.monotonic() + 600
while True:
    try:
        with urllib.request.urlopen('http://127.0.0.1:18361/health', timeout=10) as response:
            health = json.load(response)
        if health['ready'] and health['thinking'] is False:
            with open(sys.argv[1], 'x') as output:
                json.dump(health, output, indent=2)
            break
    except Exception as error:
        if time.monotonic() >= deadline:
            raise RuntimeError(f'isolated 32k service startup failed: {error}') from error
    time.sleep(2)
PY
cd "$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05"
export SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
"$ROOT/.venv/bin/python" -u "$SOURCE/original_api_batch.py" \
    --manifest "$SOURCE/configs/d2_development_40.json" \
    --base-url http://127.0.0.1:18361/v1 \
    --start-index "${START_INDEX:-0}" --stop-index "${STOP_INDEX:-2}" \
    --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" \
    --output-dir "$OUTPUT/episodes"
