#!/bin/bash
#SBATCH --job-name=libero-qwen-ctx262k
#SBATCH --partition=gpu
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
RDROOT=/public/home/sunyihan/rd_instruction_20260923
OUT="$ROOT/results/harness_v5/a1m_context_probe_20261001/service_job${SLURM_JOB_ID}"
RUNTIME="$OUT/runtime"
mkdir -p "$RUNTIME"
cp "$ROOT/scripts/a1m_context_probe_20261001/m2_api.py" "$ROOT/scripts/a1m_context_probe_20261001/m2_launch.py" "$RUNTIME/"
cd "$RUNTIME"
sha256sum m2_api.py m2_launch.py "$ROOT/scripts/run_a1m_context_service_20261001.sbatch" > "$OUT/source.sha256"
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
VENV="$RDROOT/v5_qwen36_api/.sglang-venv"
set +u
source /public/apps/anaconda3/etc/profile.d/conda.sh
conda activate "$RDROOT/v5_qwen36_api/cuda128"
set -u
export CUDA_HOME="$RDROOT/v5_qwen36_api/cuda128"
export PATH="$VENV/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$RUNTIME" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export M2_BACKEND_KIND=sglang M2_BACKEND_URL=http://127.0.0.1:18048
export A1M_BACKEND_AUDIT="$OUT/backend_responses.jsonl"
"$VENV/bin/python" -u m2_launch.py --model-path "$RDROOT/v5_models/Qwen3.6-27B-FP8" \
 --served-model-name Qwen3.6-27B-FP8 --host 127.0.0.1 --port 18048 \
 --tp-size 2 --context-length 262144 --mem-fraction-static 0.90 \
 --max-running-requests 1 --max-total-tokens 262144 --disable-cuda-graph \
 --attention-backend triton --sampling-backend pytorch --disable-radix-cache \
 --enable-nan-detection --tool-call-parser qwen3_coder --reasoning-parser qwen3 > "$OUT/sglang.log" 2>&1 &
BACKEND_PID=$!
"$VENV/bin/python" -m uvicorn m2_api:app --host 0.0.0.0 --port 18364 --no-access-log > "$OUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$BACKEND_PID" "$GATEWAY_PID" 2>/dev/null || true' EXIT
export A1M_SERVICE_OUT="$OUT"
"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import json,os,socket,time,urllib.request
out=Path(os.environ['A1M_SERVICE_OUT']);deadline=time.monotonic()+900
while True:
    try:
        with urllib.request.urlopen('http://127.0.0.1:18364/health',timeout=10) as r:h=json.load(r)
        if h.get('ready'):
            h.update(base_url=f'http://{socket.gethostname()}:18364/v1',context_length=262144,tp=2)
            (out/'ready.json').write_text(json.dumps(h,indent=2));break
    except Exception as e:last=repr(e)
    if time.monotonic()>deadline:raise RuntimeError(last)
    time.sleep(2)
PY
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$GATEWAY_PID" 2>/dev/null; do
 if test -f "$OUT/EVALUATION_DONE"; then exit 0; fi
 sleep 5
done
wait "$BACKEND_PID" "$GATEWAY_PID"
