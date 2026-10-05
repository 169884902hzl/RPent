"""Collect finished first100/class shards without changing their active array."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not 0 <= part < 18 for part in args.part) or len(set(args.part)) != len(args.part):
        raise ValueError("require distinct explicitly registered array parts0-17")
    root = Path("/public/home/sunyihan/rpent_libero_eval")
    source = root / "source_v5_grasp459_bound_safe_retry1_20261005"
    sys.path.insert(0, str(source))
    from scripts.summarize_v5_grasp449_20261005 import truth_metrics

    base = root / "results/harness_v5/grasp459_bound_safe_retry1_20261005"
    manifest = base / "preparation/full.json"
    plan = json.loads(manifest.read_text())
    output = args.output
    output.mkdir(exist_ok=False)
    pending = set(args.part)
    while pending:
        accounting = subprocess.check_output(["sacct", "-n", "-P", "--allocations", "-j", "3550",
            "--format=JobID,State,ExitCode,Elapsed"], text=True)
        states = {line.split("|")[0]: line.split("|") for line in accounting.splitlines() if line}
        for part in sorted(pending.copy()):
            job = "3550_" + str(part)
            state = states.get(job)
            if not state or state[1] in ("RUNNING", "PENDING", "COMPLETING", "CONFIGURING"):
                continue
            ledger = base / f"full_job3550/part{part}/episodes.jsonl"
            summary = base / f"full_job3550/part{part}/summary.json"
            expected = plan["cases"][part::18]
            planned = {c["name"]: c for c in expected}
            rows = list(map(json.loads, ledger.read_text().splitlines())) if ledger.exists() else []
            names = [r["case"]["name"] for r in rows]
            if len(set(names)) != len(names) or any(r["case"] != planned.get(r["case"]["name"]) for r in rows):
                raise ValueError("duplicate or changed registered first-grasp case")
            metric = truth_metrics(rows, len(expected))
            report = {"job": job, "accounting": state, "scope": "completed class shard only, not overall qualification",
                "manifest": {"path": str(manifest), "sha256": sha(manifest)},
                "ledger": {"path": str(ledger), "sha256": sha(ledger) if ledger.exists() else None},
                "summary": {"path": str(summary), "sha256": sha(summary) if summary.exists() else None},
                "source_commit": "115ba66", "collector_sha256": sha(Path(__file__)),
                "class": expected[0]["group"], "condition": expected[0]["condition"], "metrics": metric,
                "execution_errors": sum(bool(r.get("raised_error")) or r["first_receipt"].get("verification") == "execution_error" for r in rows),
                "full_six_class_qualification": False, "new_training_rows": 0}
            path = output / f"part{part}.json"
            path.write_text(json.dumps(report, indent=2) + "\n")
            receipt = {"job": job, "state": state[1], "class": report["class"], "condition": report["condition"],
                "true": metric["true_successes"], "known": metric["known_truth"],
                "wilson_95CI": metric["wilson_95CI"], "verifier_agreement": metric["verifier_agreement"],
                "confusion": metric["confusion"], "execution_errors": report["execution_errors"],
                "output": str(path), "sha256": sha(path), "qualification_complete": False}
            print(json.dumps(receipt), flush=True)
            coord = Path("/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md")
            with coord.open("a") as stream:
                stream.write("\n### Codex3 completed first100/class shard evidence\n" + json.dumps(receipt) + "\n")
            pending.remove(part)
        if pending:
            # Wait only for these already-running physical trials.
            time.sleep(30)


if __name__ == "__main__":
    main()
