"""Summarize the explicitly registered 40-episode fixed-model development run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def distribution(values: list[float]) -> dict:
    values = sorted(values)
    if not values:
        return {"n": 0, "median_s": None, "p95_s": None}
    return {
        "n": len(values),
        "median_s": statistics.median(values),
        "p95_s": values[max(0, math.ceil(0.95 * len(values)) - 1)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    expected = {(e["suite"], e["task"], e["seed"]) for e in plan["episodes"]}
    if len(expected) != 40 or len(plan["episodes"]) != 40:
        raise ValueError("requires exactly the registered D2 40 episodes")
    source = args.results / "episodes" / "episodes.jsonl"
    records = [json.loads(line) for line in source.read_text().splitlines()]
    seen = set()
    episodes = []
    wall = defaultdict(list)
    steps = defaultdict(list)
    causes = Counter()
    tools = Counter()
    by_suite = defaultdict(Counter)
    sources = []
    for row in records:
        e, result = row["episode"], row["result"]
        key = (e["suite"], e["task"], e["seed"])
        if key not in expected or key in seen:
            raise ValueError(f"unregistered or duplicate episode: {key}")
        seen.add(key)
        directory = args.results / "episodes" / f"{key[0]}_t{key[1]}_s{key[2]}"
        if directory != Path(row["output_dir"]):
            raise ValueError("output directory differs from registered identity")
        path = directory / "choices.jsonl"
        trace = []
        if path.exists():
            data = path.read_bytes()
            sources.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
            trace = [json.loads(line) for line in data.splitlines()]
        successful = bool(result.get("correct_finish"))
        subset = "success" if successful else "failure"
        eligible = bool(trace) and result.get("termination_category") != "startup_error"
        if result.get("wall_s") is not None:
            wall["all_attempted"].append(float(result["wall_s"]))
            wall[subset].append(float(result["wall_s"]))
            if eligible:
                wall["with_decisions"].append(float(result["wall_s"]))
        for decision in trace:
            tools[decision["selected"].split("(", 1)[0]] += 1
            for field in ("model_inference", "choice_request", "perception", "execution", "total"):
                value = decision["timing_s"].get(field)
                if value is not None:
                    steps[field].append(float(value))
                    steps[f"{subset}/{field}"].append(float(value))
        cause = result.get("termination_category", "startup_error")
        causes[cause] += 1
        by_suite[key[0]]["attempted"] += 1
        by_suite[key[0]]["correct_finish"] += successful
        by_suite[key[0]]["physical_success"] += bool(result.get("official_success"))
        by_suite[key[0]][cause] += 1
        episodes.append({"episode": e, "result": result, "recorded_decisions": len(trace),
                         "latency_has_decisions": eligible, "output_dir": str(directory)})
    report = {
        "purpose": "fixed2323_D2_development_timing_not_final_or_speed_claim",
        "complete": seen == expected,
        "planned": 40, "attempted": len(seen),
        "unattempted": [list(k) for k in sorted(expected - seen)],
        "model_identity": plan["model_identity"],
        "memory": "none; expert-derived memory not yet admitted",
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "ledger_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "by_suite": dict(by_suite), "terminal_counts": dict(causes),
        "episode_wall": {key: distribution(value) for key, value in wall.items()},
        "step_timing": {key: distribution(value) for key, value in steps.items()},
        "selected_tools": dict(tools),
        "latency_scope": "wall includes episode initialization; model_inference includes prompt preparation and GPU forward; total includes perception and execution",
        "speed_interpretation": "Early finish/ask_help/budget failures are retained and are not evidence of acceleration.",
        "episodes": episodes, "trace_sources": sources,
    }
    (args.results / "timing_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("episodes", "trace_sources")}, indent=2))


if __name__ == "__main__":
    main()
