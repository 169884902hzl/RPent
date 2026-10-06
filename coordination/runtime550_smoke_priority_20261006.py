"""Prioritize the submitted complete smoke without interrupting live trials."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


def utc():
    return datetime.now(timezone.utc).isoformat()


def state(job):
    result = subprocess.run(["squeue", "-r", "-h", "-j", job, "-o", "%i|%T"],
                            capture_output=True, text=True, check=True)
    return {key: value for key, value in (line.split("|", 1)
            for line in result.stdout.splitlines())}.get(job)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Existing coordination ledger; do not start twice")
    candidates = [f"{job}_{part}" for job, size in
                  ((4148, 8), (4149, 8), (4177, 8), (4178, 6))
                  for part in range(size)]
    target = [f"4186_{part}" for part in range(8)]
    record = {"target": 4186, "created_at_utc": utc(), "active": True,
              "maximum_minutes": 45, "held": [], "skipped": [], "released": [],
              "release_condition": "all eight target tasks started or terminated, or 45-minute deadline; finally cleanup",
              "running_trials_interrupted": False}

    def save():
        args.output.write_text(json.dumps(record, indent=2) + "\n")

    deadline = time.monotonic() + 45 * 60
    try:
        save()
        for job in candidates:
            current = state(job)
            if current != "PENDING":
                record["skipped"].append({"job": job, "state": current})
                continue
            result = subprocess.run(["scontrol", "hold", job], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f"hold {job}: {result.stderr}")
            record["held"].append(job)
            save()
        while True:
            not_started = [job for job in target if state(job) == "PENDING"]
            record.update(last_poll_utc=utc(), target_not_started=not_started)
            save()
            if not not_started:
                record["release_reason"] = "all target tasks first started or terminated"
                break
            if time.monotonic() >= deadline:
                record["release_reason"] = "cleanup deadline reached"
                break
            time.sleep(min(60, max(0, deadline - time.monotonic())))
    finally:
        for job in record["held"]:
            result = subprocess.run(["scontrol", "release", job], capture_output=True, text=True)
            record["released"].append({"job": job, "exit_code": result.returncode,
                                       "stderr": result.stderr.strip()})
            save()
        record.update(active=False, finished_at_utc=utc())
        save()
        print(json.dumps({"active": False, "held": len(record["held"]),
                          "released": len(record["released"]),
                          "errors": sum(row["exit_code"] != 0 for row in record["released"]),
                          "reason": record.get("release_reason", "exception cleanup")}), flush=True)


if __name__ == "__main__":
    main()
