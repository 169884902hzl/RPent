#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=130G
#SBATCH --time=08:00:00
#SBATCH --array=0-7%8
#SBATCH --job-name=libero-runtime536-smoke
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SMOKE536_SOURCE:?absolute registered snapshot required}
PREP=${SMOKE536_PREP:?absolute registered preparation directory required}
SERVICE=/public/home/sunyihan/rd_instruction_20260923/v5r_20261001/qualified_service_sources_bf097673
RD=/public/home/sunyihan/rd_instruction_20260923
OUT="$ROOT/results/harness_v5/runtime536_smoke20_20261006/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$OUT"
export PYTHONPATH="$SOURCE" LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
# CPU preflight precedes loading any GPU service and resolves every plan path.
"$ROOT/.venv/bin/python" "$SOURCE/scripts/preflight_v5_runtime536_smoke.py" --root "$ROOT" --source "$SOURCE" --preparation "$PREP" --output "$OUT/preflight.json"
cd "$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export V5R_BASE="$RD/v5_models/qwen3_5_4b_851bf6e8"
export V5R_CHECKPOINT="/public/home/sunyihan/rd_instruction_20260923/v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin"
export V5R_PACKAGE="$RD/v5r_20261001/package3072"
export V5R_TOKEN_LIMIT=3072 V5R_EXPERIMENTAL_PREFIX_FORK=0
unset V5R_CALIBRATION DECIDER_API_KEY
PORT=$("$ROOT/.venv/bin/python" -c 'from rpent.utils.daemon import pick_free_port; print(pick_free_port())')
# Same interpreter/dependency paths as the verified qualified service.
PP=/public/home/sunyihan/.cache/uv/archive-v0/9k-b95Vkiz_wwIuJtk55f:/public/home/sunyihan/.cache/uv/archive-v0/axVQBChkwnIeMnJgrBhUx:/public/home/sunyihan/.cache/uv/archive-v0/LO_N6_FRg6WZCTC8gbXPA:/public/home/sunyihan/.cache/uv/archive-v0/8M_o4LbB10dqYO670ydE2:/public/home/sunyihan/.cache/uv/archive-v0/NVAZG0lqLoni-_KahYBkO:/public/home/sunyihan/.cache/uv/archive-v0/q1XAbNv0jquFac-o3fXuk:/public/home/sunyihan/.cache/uv/archive-v0/DI6MNFXwF3R-gcgWs4wlo:/public/home/sunyihan/robot_decider/runtime/.venv/lib/python3.12/site-packages
PYTHONPATH="$SERVICE:$PP" /public/home/sunyihan/robot_decider/runtime/.venv/bin/python -m uvicorn v5r_server:app --host 127.0.0.1 --port "$PORT" > "$OUT/model_service.log" 2>&1 &
service_pid=$!
trap 'kill "$service_pid" 2>/dev/null || true; wait "$service_pid" 2>/dev/null || true' EXIT
"$ROOT/.venv/bin/python" - "$PORT" "$service_pid" "$OUT" <<'HEALTH'
import json,os,sys,time
from pathlib import Path
from urllib.request import urlopen
port,pid,out=int(sys.argv[1]),int(sys.argv[2]),Path(sys.argv[3]);deadline=time.monotonic()+600
while True:
 try:
  with urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:h=json.load(r)
 except (OSError,ValueError):
  os.kill(pid,0)
  if time.monotonic()>deadline:raise RuntimeError('Step750 service startup timed out')
  time.sleep(2);continue
 assert h['revision']=='b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb',h
 assert h['max_context_tokens']==3072 and h['model'].endswith('/candidate_step750/pytorch_model.bin'),h
 (out/'model_identity.json').write_text(json.dumps(h,indent=2)+'\n');break
HEALTH
export PYTHONPATH="$SOURCE"
for COHORT in original development; do
  if [[ "$COHORT" == original ]]; then export LIBERO_TYPE=standard; else export LIBERO_TYPE=pro; fi
  "$ROOT/.venv/bin/python" -u v5_batch_eval.py --provider systemone --choice-endpoint "http://127.0.0.1:$PORT" --manifest "$PREP/${COHORT}_part${SLURM_ARRAY_TASK_ID}.json" --choice-package "$RD/v31_package_decider_2048_socket_20260925a" --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/$COHORT"
done
