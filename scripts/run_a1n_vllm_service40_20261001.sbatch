#!/bin/bash
#SBATCH --job-name=libero-a1n-vllm40
#SBATCH --partition=gpu
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=16:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
RDROOT=/public/home/sunyihan/rd_instruction_20260923
OUT="$ROOT/results/harness_v5/a1n_vllm_development40_20261001/service_job${SLURM_JOB_ID}"
RUNTIME="$OUT/runtime"
mkdir -p "$RUNTIME"
cp "$ROOT/scripts/a1m_vllm_full_audit_20261001/m2_api.py" "$RUNTIME/"
cd "$RUNTIME"
sha256sum m2_api.py "$ROOT/scripts/run_a1n_vllm_service40_20261001.sbatch" > "$OUT/source.sha256"
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
VENV="$ROOT/runtime_vllm019_a1m_20261001"
set +u
source /public/apps/anaconda3/etc/profile.d/conda.sh
conda activate "$RDROOT/v5_qwen36_api/cuda128"
set -u
export CUDA_HOME="$RDROOT/v5_qwen36_api/cuda128"
export PATH="$VENV/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/targets/x86_64-linux/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$RUNTIME" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export M2_BACKEND_KIND=vllm M2_BACKEND_URL=http://127.0.0.1:18053
export A1M_BACKEND_AUDIT="$OUT/backend_responses.jsonl"
export A1M_NO_TOOL_REQUEST_AUDIT="$OUT/no_tool_requests.jsonl"
"$VENV/bin/vllm" serve "$RDROOT/v5_models/Qwen3.6-27B-FP8" \
 --served-model-name Qwen3.6-27B-FP8 --host 127.0.0.1 --port 18053 \
 --tensor-parallel-size 2 --max-model-len 262144 --gpu-memory-utilization 0.90 \
 --max-num-seqs 1 --max-num-batched-tokens 8192 --enforce-eager \
 --no-enable-prefix-caching --enable-auto-tool-choice \
 --tool-call-parser qwen3_coder --reasoning-parser qwen3 > "$OUT/vllm.log" 2>&1 &
BACKEND_PID=$!
"$VENV/bin/python" -m uvicorn m2_api:app --host 0.0.0.0 --port 18371 --no-access-log > "$OUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$BACKEND_PID" "$GATEWAY_PID" 2>/dev/null || true' EXIT
export A1M_SERVICE_OUT="$OUT"
"$ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
import json,os,socket,time,urllib.request
out=Path(os.environ['A1M_SERVICE_OUT']);deadline=time.monotonic()+900
while True:
    try:
        with urllib.request.urlopen('http://127.0.0.1:18371/health',timeout=10) as r:h=json.load(r)
        if h.get('ready'):
            h.update(base_url=f'http://{socket.gethostname()}:18371/v1',context_length=262144,tp=2)
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
