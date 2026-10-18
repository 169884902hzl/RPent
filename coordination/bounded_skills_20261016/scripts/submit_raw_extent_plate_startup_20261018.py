"""Queue the original plate startup in the existing first serial GPU lane."""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/public/home/sunyihan/rpent_libero_eval")
base = root / "coordination/bounded_skills_20261016"
receipt_path = base / "reports/raw_extent_plate_startup_submission_20261018.json"
assert not receipt_path.exists(), "Read the existing submission instead of duplicating it"
preparation = json.loads((base / "reports/raw_extent_preparation_20261018.json").read_text())
source = Path(preparation["snapshot"])
manifest = Path(preparation["manifest"]["path"])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == preparation["manifest"]["sha256"]
raw = subprocess.check_output(
    ["squeue", "-r", "-h", "-u", "sunyihan", "-o", "%i|%j|%T|%N"], text=True
)
ours = [row.split("|") for row in raw.splitlines() if "|rd-bounded-" in row]
running = [row for row in ours if row[2] == "RUNNING"]
assert len(running) <= 3 and all(row[3] == "node02" for row in running), running
assert any(row[0] == "8246_140" for row in running), running
arguments = [
    "sbatch", "--parsable", "--nodelist=node02", "--nice=500", "--array=160%1", "--dependency=afterany:8246_140",
    "--export=ALL,SOURCE=" + str(source) + ",SOURCE_COMMIT=" + preparation["source_commit"]
    + ",MANIFEST=" + str(manifest) + ",STARTUP=1",
    str(source / "scripts/run_bounded_21f0744_20261017.sbatch"),
]
job = subprocess.check_output(arguments, text=True).strip()
report = {
    "scope": "same-source plate startup queued behind the microwave full episode",
    "training": False, "confirmation": False, "pi05_disabled": True,
    "job": job, "arguments": arguments, "snapshot": str(source),
    "source_commit": preparation["source_commit"], "manifest": preparation["manifest"],
    "queue_before": ours, "aggregate_cap": 3, "lane": 1,
}
receipt_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("job", "source_commit", "snapshot", "lane")}))
