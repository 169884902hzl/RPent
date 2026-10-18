# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Insert the startup-verified full bowl replay in the second serial lane."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

root = Path("/public/home/sunyihan/rpent_libero_eval")
parser = argparse.ArgumentParser()
parser.add_argument("--resume-job")
args = parser.parse_args()
base = root / "coordination/bounded_skills_20261016"
receipt = json.loads(
    (base / "reports/raw_extent_preparation_20261018.json").read_text()
)
output = root / "results/bounded_skills/feasibility_20261017/job8242_6"
episodes = [json.loads(line) for line in (output / "episodes.jsonl").open()]
assert len(episodes) == 1 and episodes[0]["status"] == "startup_physical", episodes
physical = next(output.glob("*oracle*/first_physical_request.json"))
assert json.loads(physical.read_text())["sim_steps"] > 0
accounting = subprocess.check_output(
    ["sacct", "-X", "-n", "-j", "8242_6", "--format=State,ExitCode", "-P"], text=True
).strip()
assert accounting == "COMPLETED|0:0", accounting
source, manifest = Path(receipt["snapshot"]), Path(receipt["manifest"]["path"])
assert (
    hashlib.sha256(manifest.read_bytes()).hexdigest() == receipt["manifest"]["sha256"]
)
queue = subprocess.check_output(
    ["squeue", "-r", "-h", "-u", "sunyihan", "-o", "%i|%j|%T|%N"], text=True
)
ours = [row.split("|") for row in queue.splitlines() if "|rd-bounded-" in row]
running = [row for row in ours if row[2] == "RUNNING"]
assert len(running) <= 3 and all(row[3] == "node02" for row in running), running
assert any(row[0] == "8184_120" for row in running), running
for task in ("8184_180", "8184_200"):
    assert any(row[0] == task and row[2] == "PENDING" for row in ours), task
export = (
    "ALL,SOURCE="
    + str(source)
    + ",SOURCE_COMMIT="
    + receipt["source_commit"]
    + ",MANIFEST="
    + str(manifest)
    + ",STARTUP=0"
)
arguments = [
    "sbatch",
    "--parsable",
    "--nodelist=node02",
    "--nice=500",
    "--array=6%1",
    "--dependency=afterany:8184_120",
    "--export=" + export,
    str(source / "scripts/run_bounded_21f0744_20261017.sbatch"),
]
job = args.resume_job or subprocess.check_output(arguments, text=True).strip()
updates = []
if args.resume_job:
    # Recover the already submitted pending job before rewiring successors.
    # Depending first on a downstream job would form a graph cycle.
    assert any(row[0] == job + "_6" and row[2] == "PENDING" for row in ours), job
    command = ["scontrol", "update", "JobId=" + job, "Dependency=afterany:8184_120"]
    subprocess.run(command, check=True)
    updates.append(command)
for task in ("8184_180", "8184_200"):
    command = ["scontrol", "update", "JobId=" + task, "Dependency=afterany:" + job]
    subprocess.run(command, check=True)
    updates.append(command)
report = {
    "scope": "full original bowl init6 replay after identical-source/launcher physical startup",
    "confirmation": False,
    "training": False,
    "pi05_disabled": True,
    "job": job,
    "arguments": arguments,
    "updates": updates,
    "queue_before": ours,
    "recovered_existing_pending_job": args.resume_job,
    "snapshot": str(source),
    "source_commit": receipt["source_commit"],
    "manifest": receipt["manifest"],
    "startup": {
        "job": "8242_6",
        "state_exit": accounting,
        "episodes_sha256": hashlib.sha256(
            (output / "episodes.jsonl").read_bytes()
        ).hexdigest(),
        "first_physical_request": json.loads(physical.read_text()),
    },
    "aggregate_cap": 3,
    "lane": "8184_120 -> " + job + " ->8184_180/200 ->8192",
}
(base / "reports/raw_extent_full_submission_20261018.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    json.dumps(
        {
            key: value
            for key, value in report.items()
            if key not in ("updates", "queue_before")
        }
    )
)
