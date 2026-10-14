#!/usr/bin/env python3
"""Record same-launcher CPU preflight and optionally append a prepared receipt."""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--coordination-fragment", type=Path)
    parser.add_argument("--append-only", action="store_true")
    args = parser.parse_args()
    index = json.loads((args.preparation / "manifest.json").read_text())
    source = index["source_path"]
    launcher = Path(index["launcher"]["path"])
    if args.append_only:
        report_path = args.preparation / "launcher_CPU_preflight.json"
        report = json.loads(report_path.read_text())
        if report["status"] != "pass" or report["manifest_sha256"] != sha(args.preparation / "manifest.json"):
            raise SystemExit("cannot append a receipt without the exact passing preflight")
        if args.coordination_fragment is None:
            raise SystemExit("append-only requires a prepared receipt fragment")
        append_receipt(args.coordination_fragment)
        return
    records = []
    for part in range(len(index["files"])):
        env = {**os.environ, "INTERIM574_SOURCE": source,
               "INTERIM574_PREP": str(args.preparation), "INTERIM574_COHORT": "expert",
               "INTERIM574_PREFLIGHT_ONLY": "1", "SLURM_ARRAY_TASK_ID": str(part)}
        result = subprocess.run(["bash", str(launcher)], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = args.preparation / f"launcher_CPU_preflight_part{part}.log"
        log.write_text(result.stdout)
        records.append({"part": part, "exit_code": result.returncode,
                        "log": {"path": str(log), "sha256": sha(log)}})
        if result.returncode:
            print(result.stdout)
            break
    report = {"source": source, "manifest_sha256": sha(args.preparation / "manifest.json"),
              "launcher_sha256": sha(launcher), "records": records,
              "status": "pass" if len(records) == len(index["files"]) and
                        all(r["exit_code"] == 0 for r in records) else "fail",
              "gpu_initialized": False, "physical_requests": 0}
    report_path = args.preparation / "launcher_CPU_preflight.json"
    if report_path.exists():
        raise SystemExit("preflight report already exists; preserve the old evidence")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] != "pass":
        raise SystemExit(2)
    if args.coordination_fragment is not None:
        append_receipt(args.coordination_fragment)
    print(json.dumps({"status": report["status"], "report": str(report_path),
                      "sha256": sha(report_path), "parts": len(records)}))


def append_receipt(fragment_path):
    fragment = fragment_path.read_text()
    coordination = Path("/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md")
    with coordination.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        if fragment.strip() not in stream.read():
            stream.seek(0, 2)
            stream.write("\n" + fragment + "\n")
            stream.flush()
            os.fsync(stream.fileno())


if __name__ == "__main__":
    main()
