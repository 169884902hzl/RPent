#!/bin/bash
#SBATCH --job-name=libero-a1m-vllm8
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=04:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=$ROOT/source_v5_a1m_sampling_20261001
SERVICE_OUT="$ROOT/results/harness_v5/a1m_vllm_probe_20261001/service_job${SERVICE_JOB:?}"
OUT="$ROOT/results/harness_v5/a1m_vllm_probe_20261001/eval_job${SLURM_JOB_ID}"
mkdir -p "$OUT"
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
sha256sum "$ROOT/scripts/a1m_context_probe_20261001/a1m_batch.py" "$ROOT/scripts/run_a1m_vllm_eval8_20261001.sbatch" "$ROOT/configs/a1m_vllm_probe_20261001/development8.json" > "$OUT/source.sha256"
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
cd "$SOURCE"
"$ROOT/.venv/bin/python" -u "$ROOT/scripts/a1m_context_probe_20261001/a1m_batch.py" \
 --manifest "$ROOT/configs/a1m_vllm_probe_20261001/development8.json" --base-url "$BASE_URL" \
 --pause-marker "$ROOT/results/harness_v5/PAUSE_REQUESTED" --output-dir "$OUT/episodes"
touch "$SERVICE_OUT/EVALUATION_DONE"
