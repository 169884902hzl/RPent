#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-stove523-fullchunks
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
STOVE_ROOT=/public/home/sunyihan/rpent_libero_eval
STOVE523_SOURCE="${STOVE523_SOURCE:?Set the final source snapshot before submission}"
STOVE523_MANIFEST_SHA="${STOVE523_MANIFEST_SHA:?Set the registered fullchunks manifest SHA}"
STOVE_BASE="$STOVE_ROOT/results/harness_v5/stove523_fullchunks_original_20261005"
STOVE_MANIFEST="$STOVE_BASE/preparation/stove_control_fullchunks.json"
export PYTHONPATH="$STOVE523_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$STOVE_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$STOVE_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$STOVE_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$STOVE523_SOURCE"
STOVE_RUN="$STOVE_BASE/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$STOVE_RUN"
"$STOVE_ROOT/.venv/bin/python" - "$STOVE_MANIFEST" "$STOVE523_SOURCE" "$STOVE523_MANIFEST_SHA" \
  "$STOVE_RUN/source_identity_part${SLURM_ARRAY_TASK_ID}.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest, source = map(Path, sys.argv[1:3])
expected, output = sys.argv[3], Path(sys.argv[4])
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
if digest != expected:
    raise RuntimeError("registered original fullchunks manifest changed")
plan = json.loads(manifest.read_text())
files = {}
for name in ("scripts/probe_v5_stove521_endpoint.py", "scripts/probe_v5_skill501_original.py",
             "robots/libero/v5_stove_probe_env.py", "robots/libero/v5_runtime.py",
             "robots/libero/v5_stove_measurement.py", "robots/libero/v5_fixture_parts.py",
             "robots/libero/v5_env_client.py", "robots/libero/v5_env_server.py"):
    files[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
for name, key in (("scripts/probe_v5_stove521_endpoint.py", "required_probe_sha256"),
                  ("robots/libero/v5_stove_probe_env.py", "required_server_sha256"),
                  ("robots/libero/v5_stove_measurement.py", "required_stove_module_sha256")):
    if files[name] != plan[key]:
        raise RuntimeError("final source snapshot does not match registered producer: " + name)
output.write_text(json.dumps({"source": str(source), "manifest_sha256": digest, "files": files}, indent=2) + "\n")
PY
"$STOVE_ROOT/.venv/bin/python" -u -m scripts.probe_v5_stove521_endpoint \
  --manifest "$STOVE_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 \
  --output "$STOVE_RUN/part${SLURM_ARRAY_TASK_ID}"
