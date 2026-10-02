"""Count only explicitly listed development ledgers; never fill missing episodes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(paths, expected):
    rows, seen, sources = [], set(), []
    for path in paths:
        path = Path(path)
        sources.append({"path": str(path), "sha256": sha(path)})
        for entry in map(json.loads, path.read_text().splitlines()):
            episode = entry["episode"]
            key = (episode["suite"], episode["task"], episode["seed"])
            if key in seen or key not in expected:
                raise ValueError("duplicate or out-of-cohort episode")
            seen.add(key)
            result = entry["result"]
            decisions_path = Path(entry["output_dir"]) / "choices.jsonl"
            choices = list(map(json.loads, decisions_path.read_text().splitlines())) if decisions_path.exists() else []
            tags = Counter()
            previous_skill = {}
            timings = defaultdict(list)
            for choice in choices:
                receipt = choice["receipt"]
                if receipt.get("tool") == "ask_help" and previous_skill.get("grasp_verified") is False:
                    tags["help_after_failed_grasp"] += 1
                if receipt.get("error") or receipt.get("verification") == "execution_error":
                    tags["skill_execution_error"] += 1
                if receipt.get("grasp_verified") is False:
                    tags["grasp_unverified"] += 1
                if receipt.get("place_verified") is False:
                    tags["placement_unverified"] += 1
                if receipt.get("tool") not in ("ask_help", "finish", "reperceive", "retreat"):
                    previous_skill = receipt
                for kind, seconds in choice.get("timing_s", {}).items():
                    if isinstance(seconds, (int, float)):
                        timings[kind].append(seconds)
            rows.append({"episode": episode, "official_success": result["official_success"],
                         "correct_finish": result.get("correct_finish", False),
                         "status": result["status"], "termination_category": result["termination_category"],
                         "wall_s": result["wall_s"], "decisions": result.get("decisions", 0),
                         "ask_help_attempts": result.get("ask_help_attempts", 0),
                         "rejected_finish_attempts": result.get("rejected_finish_attempts", 0),
                         "observed_failure_events": dict(tags),
                         "step_timing_median_s": {k: statistics.median(v) for k, v in timings.items()},
                         "source_hashes": result["source_hashes"],
                         "choices": {"path": str(decisions_path),
                                     "sha256": sha(decisions_path) if decisions_path.exists() else None}})
    suites = defaultdict(list)
    for row in rows:
        suites[row["episode"]["suite"]].append(row)
    def counts(group):
        return {"attempted": len(group), "official_success": sum(x["official_success"] for x in group),
                "correct_finish": sum(x["correct_finish"] for x in group),
                "zero_call_infrastructure_errors": sum(x["status"] != "completed" and x["decisions"] == 0 for x in group),
                "terminal_categories": dict(Counter(x["termination_category"] for x in group)),
                "wall_median_s": statistics.median(x["wall_s"] for x in group) if group else None,
                "ask_help_attempts": sum(x["ask_help_attempts"] for x in group),
                "rejected_finish_attempts": sum(x["rejected_finish_attempts"] for x in group)}
    return {**counts(rows), "planned": len(expected), "complete": seen == expected,
            "unattempted": sorted(expected - seen), "by_suite": {k: counts(v) for k, v in suites.items()},
            "episodes": rows, "ledgers": sources,
            "scope": "development; failure events describe observed receipts and are not asserted physical root causes; HTTP round trip is distinct from server compute"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    report = {"index_sha256": sha(args.index), "script_sha256": sha(__file__), "groups": {}}
    for group, descriptor in index["groups"].items():
        manifest = Path(descriptor["manifest"])
        if sha(manifest) != descriptor["manifest_sha256"]:
            raise ValueError("cohort manifest changed")
        plan = json.loads(manifest.read_text())
        expected = {(e["suite"], e["task"], e["seed"]) for e in plan["episodes"]}
        report["groups"][group] = summarize(descriptor["ledgers"], expected)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: {x: v[x] for x in ("attempted", "official_success", "complete", "wall_median_s")}
                      for k, v in report["groups"].items()}))


if __name__ == "__main__":
    main()
