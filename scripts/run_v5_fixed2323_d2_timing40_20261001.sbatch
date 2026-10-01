#!/usr/bin/env bash
#SBATCH --job-name=libero-v5-2323-timing40
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --time=06:00:00
#SBATCH --nice=16000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_fixed2323_timing32_20261001"
OUT="$ROOT/results/harness_v5/fixed2323_d2_timing40_20261001/job${SLURM_JOB_ID}"
PACKAGE=/public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a
BASE=/public/home/sunyihan/rd_instruction_20260923/v5_models/qwen3_5_4b_851bf6e8
CHECKPOINT=/public/home/sunyihan/rd_instruction_20260923/dagger_counterfactual_sft_v2_20260928/checkpoint_dagger_counterfactual
MODEL_PY=/public/home/sunyihan/robot_decider/runtime/.venv/bin/python
RPENT_PY="$ROOT/.venv/bin/python"
mkdir -p "$OUT"
cd "$SOURCE"
export PYTHONPATH="$SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=pro
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
scontrol show job "$SLURM_JOB_ID" > "$OUT/job.txt"
nvidia-smi --query-gpu=index,uuid,memory.total,memory.used --format=csv > "$OUT/gpu_before.csv"
"$MODEL_PY" - "$OUT" <<'PY'
import json, os, platform, sys
from pathlib import Path
import torch, transformers
metadata = {
    "python": sys.executable, "python_version": platform.python_version(),
    "torch": torch.__version__, "transformers": transformers.__version__,
    "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    "slurm_job_gpus": os.environ.get("SLURM_JOB_GPUS"),
    "colocation": "fixed2323 + SAM3 + pi05 in this exclusive one-GPU allocation",
    "dtype": "bf16", "attention": "sdpa", "memory": "none",
}
(Path(sys.argv[1]) / "runtime_identity.json").write_text(json.dumps(metadata, indent=2))
PY
sha256sum "$SOURCE/qwen_choice_service.py" "$SOURCE/harness_v5_eval.py" \
 "$SOURCE/v5_batch_eval.py" "$SOURCE/robots/libero/v5_state.py" \
 "$SOURCE/robots/libero/v5_runtime.py" "$SOURCE/configs/v5_fixed2323_d2_timing40_20261001.json" \
 "$SOURCE/scripts/run_v5_fixed2323_d2_timing40_20261001.sbatch" \
 "$PACKAGE/parallel_schema.py" "$BASE/config.json" > "$OUT/source.sha256"
PORT=$("$RPENT_PY" -c 'from rpent.utils.daemon import pick_free_port; print(pick_free_port())')
"$MODEL_PY" -u "$SOURCE/qwen_choice_service.py" --model dagger2323 --package "$PACKAGE" \
 --base "$BASE" --checkpoint "$CHECKPOINT" --port "$PORT" > "$OUT/choice_service.log" 2>&1 &
service_pid=$!
trap 'kill "$service_pid" 2>/dev/null || true; wait "$service_pid" 2>/dev/null || true' EXIT
"$RPENT_PY" - "$PORT" "$service_pid" "$OUT" <<'PY'
import json, os, sys, time
from pathlib import Path
from urllib.request import urlopen
deadline = time.monotonic() + 600
port, pid, output = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
while True:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
            ready = json.load(response)
        if ready.get("status") == "ready" and ready.get("model") == "dagger2323":
            (output / "choice_ready.json").write_text(json.dumps(ready, indent=2))
            break
    except (OSError, ValueError):
        pass
    os.kill(pid, 0)
    if time.monotonic() > deadline:
        raise RuntimeError("fixed2323 Choice service did not initialize in 600 seconds")
    time.sleep(2)
PY
nvidia-smi --query-gpu=index,uuid,memory.total,memory.used --format=csv > "$OUT/gpu_service_ready.csv"
set +e
"$RPENT_PY" -u "$SOURCE/v5_batch_eval.py" \
 --manifest "$SOURCE/configs/v5_fixed2323_d2_timing40_20261001.json" \
 --provider dagger2323 --choice-package "$PACKAGE" --choice-endpoint "http://127.0.0.1:$PORT" \
 --pause-marker "$OUT/PAUSE_REQUESTED" --output-dir "$OUT/episodes"
status=$?
set -e
if [ -f "$OUT/episodes/episodes.jsonl" ]; then
 "$RPENT_PY" "$SOURCE/scripts/summarize_v5_timing40_20261001.py" \
  --manifest "$SOURCE/configs/v5_fixed2323_d2_timing40_20261001.json" --results "$OUT"
fi
exit "$status"
