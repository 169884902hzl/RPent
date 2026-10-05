#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-sam524-saved
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail

GRASP524_ROOT=/public/home/sunyihan/rpent_libero_eval
GRASP524_SOURCE="${GRASP524_SOURCE:?Parent must provide the explicit archived source snapshot}"
GRASP524_MANIFEST="$GRASP524_ROOT/results/harness_v5/grasp524_missing_points_CPU_20261005/preparation_min8/queries.json"
GRASP524_MANIFEST_SHA=b932876ebced88c224c5772c44b0e7a03b2fc7b31435025b1c2444e1d38eb977
GRASP524_RUNNER_SHA=f93cc4a81f95bc9e16832f4cd7463bda979f1030c7a242c1b118268e1e4af8bc
GRASP524_CHECKPOINT="$GRASP524_ROOT/assets/sam3/sam3.pt"
GRASP524_OUT="$GRASP524_ROOT/results/harness_v5/grasp524_missing_points_CPU_20261005/query_job${SLURM_JOB_ID:?Slurm job id required}"

export PYTHONPATH="$GRASP524_SOURCE"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$GRASP524_SOURCE"
"$GRASP524_ROOT/.venv/bin/python" - "$GRASP524_SOURCE" "$GRASP524_RUNNER_SHA" \
  "$GRASP524_MANIFEST" "$GRASP524_MANIFEST_SHA" <<'PY'
import hashlib
from pathlib import Path
import sys

source, runner_sha, manifest, manifest_sha = sys.argv[1:]
runner = Path(source) / "scripts/probe_v5_grasp524_saved_queries.py"
for path, expected in ((runner, runner_sha), (Path(manifest), manifest_sha)):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("registered source or saved-image query manifest changed: " + str(path))
PY
"$GRASP524_ROOT/.venv/bin/python" -u -m scripts.probe_v5_grasp524_saved_queries \
  --manifest "$GRASP524_MANIFEST" \
  --manifest-sha256 "$GRASP524_MANIFEST_SHA" \
  --checkpoint "$GRASP524_CHECKPOINT" \
  --output "$GRASP524_OUT"
