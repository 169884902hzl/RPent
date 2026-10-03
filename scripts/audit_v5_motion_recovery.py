"""Audit recorded motion failures and cooldown from explicit closed episodes."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from robots.libero.v5_state import Candidate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_group(group):
    ledger = Path(group["ledger"])
    if sha(ledger) != group["ledger_sha256"]:
        raise ValueError("registered episode ledger changed")
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    counts, errors, samples, traces = Counter(), Counter(), [], []
    for row in rows:
        path = Path(row["output_dir"]) / "choices.jsonl"
        before_sha = sha(path) if path.exists() else None
        events = [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []
        receipts = []
        counts["complete_episodes"] += 1
        counts["official_success"] += bool(row["result"].get("official_success"))
        result = row["result"]
        counts["infrastructure_episodes"] += result.get("termination_category") == "startup_error" or (
            result.get("status") == "error" and any(text in result.get("error", "").lower()
            for text in ("connection refused", "urlerror", "service startup", "http error")))
        for event in events:
            counts["decisions"] += 1
            context = event["request"]["context"]
            counts["failure_counts_visible"] += "candidate failures=count:type" in context
            blocked = {
                receipt.get("card_action") or Candidate(
                    receipt["tool"], receipt.get("object"), receipt.get("target"), receipt.get("mode")
                ).text()
                for receipt in receipts[-3:]
                if receipt.get("verification") == "execution_error"
            }
            leaked = sorted(blocked.intersection(event["candidates"]))
            repeated = event["selected"] in blocked
            counts["steps_with_blocked_candidate"] += bool(leaked)
            counts["blocked_action_selected"] += repeated
            receipt = event["receipt"]
            physical_failed = {Candidate(r["tool"], r.get("object"), r.get("target"), r.get("mode")).text()
                               for r in receipts[-3:] if r.get("verification") == "failed"}
            counts["physical_failed_action_reselected_within_three"] += event["selected"] in physical_failed
            counts["approach_not_reached"] += receipt.get("failure_reason") == "approach_not_reached"
            counts["wrist_pose_not_reached"] += receipt.get("failure_reason") == "wrist_pose_not_reached"
            if receipt.get("verification") == "execution_error":
                counts["execution_error_events"] += 1
                exception = re.sub(r"-?\d+\.\d+", "<number>", receipt.get("error", "unknown"))
                errors[(receipt["tool"], exception)] += 1
            if leaked or repeated:
                samples.append({"episode": row["episode"], "decision": event["decision"],
                                "selected": event["selected"], "blocked_candidates": leaked,
                                "selected_blocked": repeated, "trace": str(path)})
            receipts.append(receipt)
        if path.exists() and sha(path) != before_sha:
            raise ValueError("registered completed episode changed during audit")
        traces.append({"path": str(path), "sha256": before_sha, "decisions": len(events)})
    return {"name": group["name"], "scope": group["scope"], "ledger": str(ledger),
            "ledger_sha256": group["ledger_sha256"], "counts": dict(counts),
            "execution_errors": [{"tool": tool, "exception": error, "events": count}
                                 for (tool, error), count in errors.most_common()],
            "cooldown_violations": samples, "traces": traces}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    report = {"scope": "Recorded development motion audit, no score or label changes. "
                       "Live groups contain only completed episodes at the registered cutoff.",
              "index_sha256": sha(args.index), "script_sha256": sha(__file__),
              "groups": [audit_group(group) for group in index["groups"]],
              "new_training_rows": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"groups": [{"name": g["name"], "scope": g["scope"], "counts": g["counts"],
                                  "errors": g["execution_errors"]} for g in report["groups"]],
                      "report_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
