#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --nice=1000
#SBATCH --job-name=libero-grasp459-report
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE="$ROOT/source_v5_grasp459_bound_safe_retry1_20261005"
BASE="$ROOT/results/harness_v5/grasp459_bound_safe_retry1_20261005"
export PYTHONPATH="$SOURCE" CUDA_VISIBLE_DEVICES=""
cd "$SOURCE"
OUT="$BASE/report_job${SLURM_JOB_ID}"
mkdir "$OUT"
exec "$ROOT/.venv/bin/python" - "$BASE" "$GRASP_FORMAL_ARRAY_ID" "$OUT" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

base, array, output = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
ledgers, missing = [], []
for part in range(18):
    path = base / f"full_job{array}" / f"part{part}" / "episodes.jsonl"
    if path.is_file():
        ledgers.extend(["--ledger", str(path)])
    else:
        missing.append({"part": part, "path": str(path)})
accounting = subprocess.check_output(
    ["sacct", "-n", "-P", "-j", str(array), "--allocations", "--format=JobID,State,ExitCode,Elapsed"], text=True)
(output / "shard_accounting.json").write_text(json.dumps(
    {"array": array, "explicit_shards": 18, "missing_ledgers": missing, "accounting": accounting,
     "missing_is_unknown_not_model_failure": True}, indent=2) + "\n")
if not ledgers:
    raise RuntimeError("no physical trial ledger; infrastructure failure has no model score")
subprocess.run([sys.executable, "scripts/summarize_v5_grasp449_20261005.py",
                "--manifest", str(base / "preparation/full.json"), *ledgers,
                "--output", str(output / "report.json")], check=True)
PY
