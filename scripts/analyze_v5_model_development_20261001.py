"""Summarize observed model behavior without changing episode judgments."""

import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "mean_s": None, "median_s": None, "p95_s": None}
    return {"n": len(values), "mean_s": statistics.mean(values),
            "median_s": statistics.median(values),
            "p95_s": values[math.ceil(0.95 * len(values)) - 1]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    expected = {(e["suite"], e["task"], e["seed"]) for e in plan["episodes"]}
    ledger = args.results / "episodes" / "episodes.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines()]
    seen, episodes = set(), []
    by_suite = collections.defaultdict(collections.Counter)
    observed = collections.Counter()
    timings = collections.defaultdict(list)
    episode_wall = collections.defaultdict(list)
    tools = collections.Counter()
    for record in records:
        episode, result = record["episode"], record["result"]
        key = (episode["suite"], episode["task"], episode["seed"])
        if key not in expected or key in seen:
            raise ValueError(f"unregistered or duplicate episode {key}")
        seen.add(key)
        directory = args.results / "episodes" / f"{key[0]}_t{key[1]}_s{key[2]}"
        if directory != Path(record["output_dir"]):
            raise ValueError("output identity differs from explicit ledger")
        trace_path = directory / "choices.jsonl"
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
        selected = [row["selected"] for row in trace]
        counts = collections.Counter(action.split("(", 1)[0] for action in selected)
        tools.update(counts)
        receipts = [row.get("receipt", {}) for row in trace]
        patterns = {
            "model_ask_help": bool(selected and selected[-1] == "ask_help()"),
            "false_finish": bool(result.get("false_finish")),
            "false_finish_after_verified_place": bool(result.get("false_finish") and any(r.get("place_verified") is True for r in receipts)),
            "has_unverified_grasp": any(r.get("grasp_verified") is False for r in receipts),
            "has_unverified_place": any(r.get("place_verified") is False for r in receipts),
            "has_execution_error": any(r.get("error") or r.get("verification") == "execution_error" for r in receipts),
            "budget_exhausted": bool(result.get("budget_exhausted")),
        }
        observed.update(name for name, present in patterns.items() if present)
        longest_repeat = current_repeat = 0
        previous = None
        for action in selected:
            current_repeat = current_repeat + 1 if action == previous else 1
            longest_repeat = max(longest_repeat, current_repeat)
            previous = action
        group = "success" if result.get("correct_finish") else "failure"
        if result.get("wall_s") is not None:
            value = float(result["wall_s"])
            episode_wall["all_attempted"].append(value)
            episode_wall[group].append(value)
        for row in trace:
            for name, value in row.get("timing_s", {}).items():
                if value is not None:
                    timings[name].append(float(value))
                    timings[f"{group}/{name}"].append(float(value))
        count = by_suite[key[0]]
        count["attempted"] += 1
        for name in ("official_success", "correct_finish", "false_finish", "budget_exhausted"):
            count[name] += bool(result.get(name))
        count.update(name for name, present in patterns.items() if present and name not in ("false_finish", "budget_exhausted"))
        episodes.append({"episode": episode, "result": result,
                         "observed_patterns": patterns, "selected_tools": dict(counts),
                         "action_sequence": selected, "longest_identical_choice_run": longest_repeat,
                         "trace_path": str(trace_path), "trace_sha256": sha(trace_path) if trace_path.exists() else None,
                         "last_choice": trace[-1] if trace else None})
    wall = {key: distribution(values) for key, values in episode_wall.items()}
    complete = seen == expected
    mean = wall.get("all_attempted", {}).get("mean_s")
    report = {
        "purpose": "development diagnosis only; not frozen evaluation or a stop-gate judgment",
        "complete": complete, "planned": len(expected), "attempted": len(seen),
        "manifest_path": str(args.manifest), "manifest_sha256": sha(args.manifest),
        "ledger_path": str(ledger), "ledger_sha256": sha(ledger), "script_sha256": sha(Path(__file__)),
        "by_suite": dict(by_suite), "observed_episode_patterns": dict(observed),
        "pattern_caveat": "Nonexclusive observations, not established physical root causes. Original terminal categories are preserved. Model ask_help does not prove perception failure.",
        "selected_tools": dict(tools), "episode_wall": wall,
        "step_timing": {key: distribution(values) for key, values in timings.items()},
        "worker_projection": {"gpu_count": 1, "episodes800_gpu_hours": mean * 800 / 3600 if complete and mean is not None else None,
                              "episodes80_gpu_hours": mean * 80 / 3600 if complete and mean is not None else None,
                              "scope": "linear wall-time projection of one colocated worker GPU; excludes queue, shared model startup, and any remote decision-model service. Failure-heavy timing is not a success speed claim."},
        "decision_latency_scope": "local model_inference is service computation; Jev http_round_trip is HTTP wall time. total includes perception and execution; missing fields remain missing.",
        "episodes": episodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "episodes"}, indent=2))


if __name__ == "__main__":
    main()
