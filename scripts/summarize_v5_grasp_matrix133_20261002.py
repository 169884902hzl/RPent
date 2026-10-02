"""Compare the three explicitly registered original-task grasp conditions."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    focus = {(e["suite"], e["task"], e["seed"]): e["focus_category"] for e in index["selection"]}
    report = {"purpose": "paired_original_only_development_not_training_or_frozen_scores",
              "index_sha256": hashlib.sha256(args.index.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "conditions": {}}
    for plan in index["plans"]:
        path = Path(plan["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != plan["sha256"]:
            raise ValueError("registered plan changed")
        root = args.results / plan["condition"]
        ledger = root / "episodes.jsonl"
        by_category = defaultdict(Counter)
        counts, episodes, seen, walls = Counter(), [], set(), []
        for line in ledger.read_text().splitlines():
            record = json.loads(line)
            e, result = record["episode"], record["result"]
            identity = (e["suite"], e["task"], e["seed"])
            if identity not in focus or identity in seen:
                raise ValueError("duplicate or unregistered episode")
            seen.add(identity)
            counts[result["termination_category"]] += 1
            walls.append(result["wall_s"])
            trace_path = Path(record["output_dir"]) / "choices.jsonl"
            attempts, focus_attempts = [], []
            for row in map(json.loads, trace_path.read_text().splitlines()):
                receipt = row["receipt"]
                if receipt.get("tool") not in ("grasp", "regrasp_restage"):
                    continue
                name = next((m["name"] for m in row["measurements"] if m["id"] == receipt.get("object")), "unknown")
                c = by_category[name]
                c["attempts"] += 1
                c["measured_verified"] += receipt.get("grasp_verified") is True
                c["execution_error"] += bool(receipt.get("error"))
                attempt = {"name": name, "decision": row["decision"], "selected": row["selected"],
                           "receipt": receipt, "motion_evidence": row.get("motion_evidence")}
                attempts.append(attempt)
                if name == focus[identity]:
                    focus_attempts.append(attempt)
            episodes.append({"episode": e, "focus_category": focus[identity],
                "physical_success": bool(result.get("official_success")),
                "correct_finish": bool(result.get("correct_finish")),
                "termination_category": result["termination_category"], "wall_s": result["wall_s"],
                "first_focus_grasp_verified": focus_attempts[0]["receipt"].get("grasp_verified") if focus_attempts else None,
                "grasp_attempts": attempts, "choices_path": str(trace_path),
                "choices_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest()})
        report["conditions"][plan["condition"]] = {
            "complete": seen == set(focus), "attempted": len(seen), "planned": len(focus),
            "physical_success": sum(e["physical_success"] for e in episodes),
            "correct_finish": sum(e["correct_finish"] for e in episodes),
            "terminal_counts": dict(counts), "wall_median_s": statistics.median(walls) if walls else None,
            "by_category": {k: dict(v) for k, v in sorted(by_category.items())}, "episodes": episodes}
    report["complete"] = all(r["complete"] for r in report["conditions"].values())
    report["verification_scope"] = "Visual lift/gripper verification; official solved reported separately; no simulation grasp predicate invented"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({k: {n: v for n, v in result.items() if n != "episodes"} for k, result in report["conditions"].items()}, indent=2))


if __name__ == "__main__":
    main()
