"""Compare original furniture receipts with their recorded physical labels."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    episodes = list(map(json.loads, args.ledger.read_text().splitlines()))
    seen, rows, sources = set(), [], []
    counts, endpoints, placement = Counter(), Counter(), Counter()
    by_task = defaultdict(Counter)
    for episode in episodes:
        identity, result = episode["episode"], episode["result"]
        key = tuple(identity[k] for k in ("suite", "task", "seed"))
        assert key not in seen
        assert key[0] in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
        assert 0 <= key[2] < 5
        seen.add(key)
        path = Path(episode["output_dir"]) / "choices.jsonl"
        trace = list(map(json.loads, path.read_text().splitlines()))
        assert len(trace) == result["decisions"]
        sources.append({"path": str(path), "sha256": sha(path)})
        actions, errors, stops = Counter(), Counter(), Counter()
        unknown, verified, false_positive = 0, 0, 0
        for event in trace:
            receipt = event["receipt"]
            tool = receipt["tool"]
            actions[tool] += 1
            if receipt.get("error"):
                errors[receipt["error"].split(":", 1)[0]] += 1
            if tool == "articulate":
                stops[str(receipt.get("stop"))] += 1
                measured = receipt.get("articulate_verified")
                truth = (event.get("predicate_verification_evidence") or {}).get("physical_articulation_predicate")
                unknown += measured is None
                verified += measured is True
                evidence = (event.get("verification_measurements") or {}).get("articulation") or {}
                endpoints["reason:" + str(evidence.get("reason", "measured"))] += 1
                endpoints["truth_unknown"] += truth is None
                endpoints["measurement_unknown"] += measured is None
                if measured is not None and truth is not None:
                    endpoints["tp" if measured and truth else "fp" if measured else "fn" if truth else "tn"] += 1
            if tool in ("place", "adjust_place"):
                truth = (event.get("predicate_verification_evidence") or {}).get("physical_placement_predicate")
                measured = receipt.get("place_verified")
                placement["truth_unknown"] += truth is None
                if truth is not None and measured is not None:
                    placement["tp" if measured and truth else "fp" if measured else "fn" if truth else "tn"] += 1
                    false_positive += measured is True and truth is False
        if result["official_success"]:
            cause = "official_success"
        elif actions["articulate"] >= 10 and verified == 0:
            cause = "repeated_articulate_without_verified_endpoint"
        elif actions["ask_help"] and any(t["receipt"].get("tool") == "grasp" for t in trace):
            cause = "grasp_failure_followed_by_view_recovery_budget"
        elif actions["ask_help"] and not actions["articulate"] and not actions["grasp"]:
            cause = "no_bound_goal_action_followed_by_view_recovery_budget"
        else:
            cause = "remaining_unresolved"
        counts[cause] += 1
        group = by_task[f"{key[0]}/task{key[1]}"]
        group["episodes"] += 1
        group["official_success"] += bool(result["official_success"])
        group["correct_finish"] += bool(result["correct_finish"])
        rows.append({"episode": identity, "official_success": result["official_success"],
                     "correct_finish": result["correct_finish"], "recorded_termination": result["termination_category"],
                     "observed_failure_pattern": cause, "actions": dict(actions), "error_types": dict(errors),
                     "articulate_stops": dict(stops), "articulate_unknown": unknown, "articulate_verified": verified,
                     "place_false_positive_events": false_positive,
                     "wall_s": result["wall_s"], "source": str(path),
                     "first_selection": trace[0]["selected"] if trace else None,
                     "last_selection": trace[-1]["selected"] if trace else None})
    tp, fp, fn = endpoints["tp"], endpoints["fp"], endpoints["fn"]
    report = {"scope": "Original-task recorded physical labels only; unknown measurements are excluded from precision. "
                       "Observed failure patterns are mutually exclusive descriptions, not proven physical causes. "
                       "One task can finish without reaching articulation; no existing result or training label is changed.",
              "ledger": str(args.ledger), "ledger_sha256": sha(args.ledger), "script_sha256": sha(__file__),
              "episodes": len(rows), "official_success": sum(r["official_success"] for r in rows),
              "correct_finish": sum(r["correct_finish"] for r in rows), "failure_patterns": dict(counts),
              "by_task": {k: dict(v) for k, v in by_task.items()},
              "wall_median_s": statistics.median(r["wall_s"] for r in rows),
              "articulation_comparison": {"counts": dict(endpoints),
                  "precision": tp / (tp + fp) if tp + fp else None,
                  "recall": tp / (tp + fn) if tp + fn else None},
              "placement_comparison": dict(placement), "sources": sources, "records": rows}
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("sources", "records", "scope")}))
    print("REPORT_SHA256", sha(args.output))


if __name__ == "__main__":
    main()
