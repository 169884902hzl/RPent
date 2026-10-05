#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-2%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-fixture526-original
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
FIXTURE_ROOT=/public/home/sunyihan/rpent_libero_eval
FIXTURE526_SOURCE="${FIXTURE526_SOURCE:?Set the final source snapshot}"
FIXTURE526_MANIFEST_SHA="${FIXTURE526_MANIFEST_SHA:?Set the registered manifest SHA}"
FIXTURE_BASE="$FIXTURE_ROOT/results/harness_v5/fixture526_original_direction_20261005"
FIXTURE_MANIFEST="$FIXTURE_BASE/preparation/fixtures_direction.json"
export PYTHONPATH="$FIXTURE526_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$FIXTURE_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$FIXTURE_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$FIXTURE_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$FIXTURE526_SOURCE"
FIXTURE_RUN="$FIXTURE_BASE/probe_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$FIXTURE_RUN"
"$FIXTURE_ROOT/.venv/bin/python" - "$FIXTURE_MANIFEST" "$FIXTURE526_SOURCE" "$FIXTURE526_MANIFEST_SHA" \
  "$FIXTURE_RUN/source_identity_part${SLURM_ARRAY_TASK_ID}.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
manifest, source = map(Path, sys.argv[1:3])
expected, output = sys.argv[3], Path(sys.argv[4])
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
if digest != expected:
    raise RuntimeError("registered original fixture direction experiment changed")
plan = json.loads(manifest.read_text())
files = {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in (
    "scripts/probe_v5_fixture526_original.py", "scripts/probe_v5_skill501_original.py",
    "robots/libero/v5_fixture_probe_env.py",
    "robots/libero/v5_fixture_parts.py", "robots/libero/v5_runtime.py", "robots/libero/v5_verification.py")}
if files["robots/libero/v5_fixture_parts.py"] != plan["geometry_module_sha256"] or files[
        "scripts/probe_v5_fixture526_original.py"] != plan["producer_sha256"]:
    raise RuntimeError("source snapshot does not contain the registered fixture producer")
if files["robots/libero/v5_fixture_probe_env.py"] != plan["diagnostic_server_sha256"]:
    raise RuntimeError("fixed full-chunk fixture diagnostic server changed")
output.write_text(json.dumps({"source": str(source), "manifest_sha256": digest, "files": files}, indent=2)+"\n")
PY
"$FIXTURE_ROOT/.venv/bin/python" -u -m scripts.probe_v5_fixture526_original \
  --manifest "$FIXTURE_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 3 \
  --output "$FIXTURE_RUN/part${SLURM_ARRAY_TASK_ID}"
