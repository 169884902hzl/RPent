#!/usr/bin/env bash
#SBATCH --job-name=libero-d2-qwen32k
#SBATCH --partition=gpu
#SBATCH --nodelist=node01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
RDROOT=/public/home/sunyihan/rd_instruction_20260923
OUTPUT="$ROOT/results/harness_v5/d2_a1n_service_20260930/job${SLURM_JOB_ID}"
RUNTIME="$OUTPUT/runtime"
mkdir -p "$RUNTIME"
cp "$RDROOT/m1_b2_20260929/m2_api.py" "$RDROOT/m1_b2_20260929/m2_launch.py" "$RUNTIME/"
cp "$RDROOT/v5_models/Qwen3.6-27B-FP8/DOWNLOAD_MANIFEST.json" "$OUTPUT/model_manifest.json"
cd "$RUNTIME"
sha256sum m2_api.py m2_launch.py > "$OUTPUT/service_source.sha256"
test "$(sha256sum m2_api.py | cut -d' ' -f1)" = 861c41bb3c9e789fabe6c5d331c06bc1cb56e3570c01b970592d6e19e4121653
test "$(sha256sum m2_launch.py | cut -d' ' -f1)" = 97296b7a21806fc656ad29c7c5b196ef781b15b08687d5bad532109e49baeb9d
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
export M2_BACKEND_KIND=sglang M2_BACKEND_URL=http://127.0.0.1:18037
"$VENV/bin/python" -u "$RUNTIME/m2_launch.py" \
    --model-path "$RDROOT/v5_models/Qwen3.6-27B-FP8" \
    --served-model-name Qwen3.6-27B-FP8 --host 127.0.0.1 --port 18037 \
    --tp-size 1 --context-length 32768 --mem-fraction-static 0.92 \
    --max-running-requests 1 --max-total-tokens 32768 --disable-cuda-graph \
    --attention-backend triton --sampling-backend pytorch \
    --disable-radix-cache --enable-nan-detection \
    --tool-call-parser qwen3_coder --reasoning-parser qwen3 > "$OUTPUT/sglang.log" 2>&1 &
BACKEND_PID=$!
"$VENV/bin/python" -m uvicorn m2_api:app --host 0.0.0.0 --port 18361 --no-access-log > "$OUTPUT/gateway.log" 2>&1 &
GATEWAY_PID=$!
trap 'kill "$BACKEND_PID" "$GATEWAY_PID" 2>/dev/null || true' EXIT
wait -n "$BACKEND_PID" "$GATEWAY_PID"
