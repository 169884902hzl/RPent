#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-2%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-fixture517-smoke
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
SKILL_ROOT=/public/home/sunyihan/rpent_libero_eval
SKILL_SOURCE="${SKILL_SOURCE:?Set the final source snapshot path before submission}"
SKILL_BASE="$SKILL_ROOT/results/harness_v5/skill517_fixture_measurement_smoke_20261005"
SKILL_MANIFEST="$SKILL_BASE/preparation/fixtures_smoke.json"
export PYTHONPATH="$SKILL_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$SKILL_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$SKILL_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$SKILL_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$SKILL_SOURCE"
SKILL_RUN="$SKILL_BASE/smoke_job${SLURM_ARRAY_JOB_ID}"
mkdir -p "$SKILL_RUN"
"$SKILL_ROOT/.venv/bin/python" - "$SKILL_MANIFEST" "$SKILL_SOURCE" \
  "$SKILL_RUN/source_identity_part${SLURM_ARRAY_TASK_ID}.json" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest, source, output = map(Path, sys.argv[1:])
digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
if digest != "9052fe260d7b552009b8f1f9fe1154384da533393eae7d0505ad02c4751aeba8":
    raise RuntimeError("registered fixture development smoke changed")
plan = json.loads(manifest.read_text())
module = source / "robots/libero/v5_fixture_parts.py"
if hashlib.sha256(module.read_bytes()).hexdigest() != plan["geometry_module_sha256"]:
    raise RuntimeError("final source snapshot does not contain the registered fixture measurement correction")
identity = {"source": str(source), "manifest_sha256": digest,
            "geometry_commit": plan["geometry_commit"], "files": {}}
for name in ("scripts/probe_v5_skill501_original.py", "robots/libero/v5_fixture_parts.py",
             "robots/libero/v5_runtime.py", "robots/libero/v5_verification.py"):
    identity["files"][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
output.write_text(json.dumps(identity, indent=2) + "\n")
PY
"$SKILL_ROOT/.venv/bin/python" -u -m scripts.probe_v5_skill501_original \
  --manifest "$SKILL_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 3 \
  --output "$SKILL_RUN/part${SLURM_ARRAY_TASK_ID}"
