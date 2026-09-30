#!/usr/bin/env bash
#SBATCH --job-name=libero-d2-qwen-official
#SBATCH --partition=gpu
#SBATCH --nodelist=node01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
RDROOT=/public/home/sunyihan/rd_instruction_20260923
OUTPUT="$ROOT/results/harness_v5/d2_a1n_service_official_20260930/job${SLURM_JOB_ID}"
RUNTIME="$OUTPUT/runtime"
mkdir -p "$RUNTIME"
cp "$RDROOT/m1_b2_20260929/m2_api.py" "$RDROOT/m1_b2_20260929/m2_launch.py" "$RUNTIME/"
cd "$RUNTIME"
sha256sum m2_api.py m2_launch.py > "$OUTPUT/service_source.sha256"
cat > "$OUTPUT/alignment_config.json" <<JSON
{"source_commit":"7e24d16","backend":"sglang","official_reference":"docs/source-en/rst_source/usage/configure_planner.rst","model":"Qwen3.6-27B-FP8","context_length":49152,"max_total_tokens":49152,"max_completion_tokens":8192,"reasoning_parser":"qwen3","tool_call_parser":"qwen3_coder","enable_auto_tool_choice":true,"gateway_enable_thinking":false,"memory":"empty local MEMORY.md","continuation_injection":false,"port":18362}
JSON
VENV="$RDROOT/v5_qwen36_api/.sglang-venv"
set +u
source /public/apps/anaconda3/etc/profile.d/conda.sh
conda activate "$RDROOT/v5_qwen36_api/cuda128"
set -u
export CUDA_HOME="$RDROOT/v5_qwen36_api/cuda128"
export PATH="$VENV/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$RUNTIME"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export M2_BACKEND_KIND=sglang M2_BACKEND_URL=http://127.0.0.1:18038
"$VENV/bin/python" -u "$RUNTIME/m2_launch.py" \
  --model-path "$RDROOT/v5_models/Qwen3.6-27B-FP8" \
  --served-model-name Qwen3.6-27B-FP8 --host 127.0.0.1 --port 18038 \
  --tp-size 1 --context-length 49152 --mem-fraction-static 0.90 \
  --max-running-requests 1 --max-total-tokens 49152 --disable-cuda-graph \
  --attention-backend triton --sampling-backend pytorch \
  --disable-radix-cache --enable-nan-detection \
  --tool-call-parser qwen3_coder --reasoning-parser qwen3 > "$OUTPUT/sglang.log" 2>&1 &
BACKEND_PID=$!
"$VENV/bin/python" -m uvicorn m2_api:app --host 0.0.0.0 --port 18362 --no-access-log > "$OUTPUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$BACKEND_PID" "$GATEWAY_PID" 2>/dev/null || true' EXIT
"$ROOT/.venv/bin/python" - "$OUTPUT/health.json" <<'PY'
import json, sys, time, urllib.request
out = sys.argv[1]; deadline = time.monotonic() + 900
while True:
    try:
        with urllib.request.urlopen('http://127.0.0.1:18362/health', timeout=10) as r:
            h = json.load(r)
        if h.get('ready') and h.get('thinking') is False:
            json.dump(h, open(out, 'w'), indent=2); break
    except Exception as e:
        last = repr(e)
    if time.monotonic() >= deadline:
        raise RuntimeError(f'official service startup failed: {last}')
    time.sleep(2)
PY
wait -n "$BACKEND_PID" "$GATEWAY_PID"
