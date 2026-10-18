"""Run the startup-verified microwave-open episode with measured three-dimensional handle axis."""

import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/public/home/sunyihan/rpent_libero_eval")
base = root / "coordination/bounded_skills_20261016"
receipt_path = base / "reports/handle_axis_microwave_full_submission_20261018.json"
assert not receipt_path.exists(), "Read the existing submission instead of duplicating it"
preparation = json.loads((base / "reports/handle_axis_preparation_20261018.json").read_text())
close_full = json.loads((base / "reports/contact_interval_microwave_full_submission_20261018.json").read_text())
predecessor = close_full['job'].split(';')[0]+'_120'
source = Path(preparation["snapshot"])
manifest = Path(preparation["manifest"]["path"])
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == preparation["manifest"]["sha256"]
startup = root / "results/bounded_skills/feasibility_20261017/job8253_140"
rows = [json.loads(line) for line in (startup / "episodes.jsonl").open()]
assert len(rows) == 1 and rows[0]["status"] == "startup_physical"
physical = next(startup.glob("*oracle*/first_physical_request.json"))
assert json.loads(physical.read_text())["sim_steps"] > 0
accounting = subprocess.check_output(
    ["sacct", "-X", "-n", "-j", "8253_140", "--format=State,ExitCode", "-P"], text=True
).strip()
assert accounting == "COMPLETED|0:0", accounting
raw = subprocess.check_output(
    ["squeue", "-r", "-h", "-u", "sunyihan", "-o", "%i|%j|%T|%N"], text=True
)
ours = [row.split("|") for row in raw.splitlines() if "|rd-bounded-" in row]
running = [row for row in ours if row[2] == "RUNNING"]
assert len(running) <= 3 and all(row[3] == "node02" for row in running), running
arguments = [
    "sbatch", "--parsable", "--nodelist=node02", "--nice=500", "--array=140%1",
    '--dependency=afterany:'+predecessor,
    "--export=ALL,SOURCE=" + str(source) + ",SOURCE_COMMIT=" + preparation["source_commit"]
    + ",MANIFEST=" + str(manifest) + ",STARTUP=0",
    str(source / "scripts/run_bounded_21f0744_20261017.sbatch"),
]
job = subprocess.check_output(arguments, text=True).strip()
report = {
    "scope": "full original microwave-open oracle replay after same-source physical startup",
    "training": False, "confirmation": False, "pi05_disabled": True,
    "job": job, "arguments": arguments, "snapshot": str(source),
    "source_commit": preparation["source_commit"], "manifest": preparation["manifest"],
    "startup": {"job": "8253_140", "state_exit": accounting,
                "first_physical_request": json.loads(physical.read_text()),
                "episode": rows[0]},
    "queue_before": ours, "aggregate_cap": 3, "lane": 1,
}
receipt_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("job", "source_commit", "snapshot", "lane")}))
