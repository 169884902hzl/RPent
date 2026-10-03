"""Compare explicit before/after first-grasp ledgers, preserving every failure."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read_group(root):
    ledger = root / "episodes.jsonl"
    records = []
    for line in ledger.read_text().splitlines():
        row = json.loads(line)
        path = Path(row["output_dir"]) / "choices.jsonl"
        trace = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
        if len(trace) > 1:
            raise ValueError("first-grasp probe contains multiple decisions")
        event = trace[0] if trace else {}
        receipt = event.get("receipt", {})
        attempted = receipt.get("tool") == "grasp"
        target = next((e["name"] for e in event.get("measurements", [])
                       if e["id"] == receipt.get("object")), None)
        records.append({"episode": row["episode"], "grasp_attempted": attempted,
                        "object_category": target, "grasp_verified": receipt.get("grasp_verified") is True,
                        "execution_error": receipt.get("verification") == "execution_error",
                        "waypoint_error": "servo did not reach measured waypoint" in str(receipt),
                        "recoverable_approach_failure": receipt.get("failure_reason") == "approach_not_reached",
                        "receipt": receipt, "result": row["result"], "trace": str(path),
                        "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None})
    valid = [r for r in records if r["grasp_attempted"]]
    counts = {k: sum(r[k] for r in valid) for k in
              ("grasp_verified", "execution_error", "waypoint_error", "recoverable_approach_failure")}
    return {"episodes": records, "planned_attempts_in_ledger": len(records),
            "valid_first_grasps": len(valid), "not_grasped_or_startup": len(records) - len(valid),
            "counts": counts, "rates_over_valid_first_grasps":
            {k: v / len(valid) if valid else None for k, v in counts.items()},
            "object_category_counts": dict(Counter(r["object_category"] for r in valid)),
            "ledger": str(ledger), "ledger_sha256": hashlib.sha256(ledger.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before, after = read_group(args.before), read_group(args.after)
    identity = lambda r: tuple(r["episode"][k] for k in ("suite", "task", "seed"))
    old = {identity(r): r for r in before["episodes"]}
    new = {identity(r): r for r in after["episodes"]}
    if old.keys() != new.keys():
        raise ValueError("paired original-scene coverage differs")
    pairs = [{"identity": key, "before": old[key], "after": new[key]}
             for key in old]
    report = {"scope": "Original first-grasp comparison, not full-task scores. Same scene/init, fresh perception and Pi05 executions.",
              "before": before, "after": after, "pairs": pairs,
              "at_least_50_valid_grasps_each": min(before["valid_first_grasps"], after["valid_first_grasps"]) >= 50,
              "new_training_rows": 0}
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
