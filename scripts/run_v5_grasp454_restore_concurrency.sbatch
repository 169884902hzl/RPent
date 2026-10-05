#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --job-name=libero-grasp454-restore
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
python3 - <<'PY'
import datetime
import os
from pathlib import Path
import subprocess

subprocess.run(["scontrol", "update", "JobId=3436", "ArrayTaskThrottle=2"], capture_output=True, text=True)
identity = subprocess.run(["scontrol", "show", "job", "3436", "-o"], capture_output=True, text=True)
if identity.returncode == 0:
    remaining = [line for line in identity.stdout.splitlines()
                 if "JobState=PENDING" in line or "JobState=RUNNING" in line]
    if any("ArrayTaskThrottle=2" not in line for line in remaining):
        raise RuntimeError("grasp449 concurrency restoration was not applied")
else:
    result = subprocess.check_output(["sacct", "-n", "-P", "-j", "3436", "--allocations",
                                      "--format=JobID,State"], text=True)
    if any(line.split("|")[1] in ("PENDING", "RUNNING", "COMPLETING")
           for line in result.splitlines() if "|" in line):
        raise RuntimeError("running array identity unavailable after restoration")
stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
with Path("/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md").open("a") as f:
    f.write(f"\n- Codex3 restoration job{os.environ['SLURM_JOB_ID']} {stamp}: "
            "repaired truth smoke exited; remaining3436 concurrency restored to2 and verified. "
            "No episode or source modified.\n")
print("3436 restored or already terminal")
PY
