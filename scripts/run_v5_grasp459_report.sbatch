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
SOURCE="${GRASP_REPORT_SOURCE:?set GRASP_REPORT_SOURCE to the report source snapshot}"
BASE="$ROOT/results/harness_v5/grasp459_bound_safe_retry1_20261005"
export PYTHONPATH="$SOURCE" CUDA_VISIBLE_DEVICES=""
cd "$SOURCE"
OUT="$BASE/report_job${SLURM_JOB_ID}"
mkdir "$OUT"
exec "$ROOT/.venv/bin/python" - "$BASE" "$GRASP_FORMAL_ARRAY_ID" "$OUT" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

base, array, output = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
manifest = base / "preparation/full.json"
plan = json.loads(manifest.read_text())
ledgers, missing, shards = [], [], []
for part in range(18):
    path = base / f"full_job{array}" / f"part{part}" / "episodes.jsonl"
    expected = {case["name"] for case in plan["cases"][part::18]}
    shard = {"part": part, "path": str(path), "planned": len(expected)}
    if path.is_file():
        ledgers.extend(["--ledger", str(path)])
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        names = {row["case"]["name"] for row in rows}
        shard.update(recorded=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     missing_trials=sorted(expected - names), unexpected_trials=sorted(names - expected),
                     unknown_truth=sum(not isinstance(row.get("true_sustained_grasp"), bool) for row in rows),
                     complete=len(rows) == len(expected) and names == expected)
    else:
        missing.append({"part": part, "path": str(path)})
        shard.update(recorded=0, missing_trials=sorted(expected), unexpected_trials=[],
                     unknown_truth=0, complete=False)
    shards.append(shard)
(output / "shard_accounting.json").write_text(json.dumps(
    {"array": array, "explicit_shards": 18, "missing_ledgers": missing, "shards": shards,
     "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
     "report_source": str(Path.cwd()), "accounting": None,
     "accounting_status": "not queried on compute node; verify and attach from login node separately",
     "missing_is_unknown_not_model_failure": True}, indent=2) + "\n")
if not ledgers:
    raise RuntimeError("no physical trial ledger; infrastructure failure has no model score")
subprocess.run([sys.executable, "scripts/summarize_v5_grasp449_20261005.py",
                "--manifest", str(manifest), *ledgers,
                "--output", str(output / "report.json")], check=True)
if any(not shard["complete"] or shard["unknown_truth"] for shard in shards):
    raise RuntimeError("physical ledgers incomplete or truth unknown; report retained without model-failure imputation")
PY
