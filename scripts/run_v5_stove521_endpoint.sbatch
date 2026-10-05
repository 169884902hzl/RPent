#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-3%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-stove521-endpoint
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
STOVE_ROOT=/public/home/sunyihan/rpent_libero_eval
SKILL_SOURCE="${SKILL_SOURCE:?Set the final source snapshot path before submission}"
STOVE_BASE="$STOVE_ROOT/results/harness_v5/stove521_endpoint_original_20261005"
STOVE_MANIFEST="$STOVE_BASE/preparation/stove_control.json"
export PYTHONPATH="$SKILL_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$STOVE_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$STOVE_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$STOVE_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SKILL_SOURCE"
STOVE_RUN="$STOVE_BASE/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$STOVE_RUN"
"$STOVE_ROOT/.venv/bin/python" - "$STOVE_MANIFEST" "$SKILL_SOURCE" \
  "$STOVE_RUN/source_identity_part${SLURM_ARRAY_TASK_ID}.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest, source, output = map(Path, sys.argv[1:])
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
if digest != "2b6480fad843429117c4218dc1615e506b2945df02dbf2196e816789be088185":
    raise RuntimeError("registered original stove measurement experiment changed")
plan = json.loads(manifest.read_text())
module = source / "robots/libero/v5_stove_measurement.py"
if hashlib.sha256(module.read_bytes()).hexdigest() != plan["required_stove_module_sha256"]:
    raise RuntimeError("final snapshot does not contain the corrected stove measurement module")
identity = {"source": str(source), "manifest_sha256": digest, "files": {}}
for name in ("scripts/probe_v5_stove521_endpoint.py", "scripts/probe_v5_skill501_original.py",
             "robots/libero/v5_runtime.py", "robots/libero/v5_stove_measurement.py",
             "robots/libero/v5_fixture_parts.py", "robots/libero/v5_env_client.py"):
    identity["files"][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
output.write_text(json.dumps(identity, indent=2) + "\n")
PY
"$STOVE_ROOT/.venv/bin/python" -u -m scripts.probe_v5_stove521_endpoint \
  --manifest "$STOVE_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 \
  --output "$STOVE_RUN/part${SLURM_ARRAY_TASK_ID}"
