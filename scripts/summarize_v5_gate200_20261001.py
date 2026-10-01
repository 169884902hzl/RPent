"""Summarize the two explicitly declared original-task expert shards."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--array-job", required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    expected = {(e["suite"], e["task"], e["seed"]) for e in plan["episodes"]}
    if len(expected) != 200 or len(plan["episodes"]) != 200:
        raise ValueError("expected exactly 200 distinct original development episodes")
    categories = {
        "completion_judgment", "no_legal_candidate", "perception_missing_object",
        "skill_execution_failure", "over_token", "budget_exhausted", "startup_error",
    }
    sources = []
    episodes = []
    requests = []
    missing = []
    seen = set()
    by_suite = defaultdict(Counter)
    by_task = defaultdict(Counter)

    def read(path: Path) -> bytes:
        data = path.read_bytes()
        sources.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
        return data

    for shard in range(2):
        root = args.results_root / f"job{args.array_job}_task{shard}"
        ledger = root / "episodes.jsonl"
        if not ledger.exists():
            missing.append(str(ledger))
            continue
        for line in read(ledger).splitlines():
            row = json.loads(line)
            episode = row["episode"]
            key = (episode["suite"], episode["task"], episode["seed"])
            if key not in expected or key in seen:
                raise ValueError(f"unplanned or duplicate episode: {key}")
            seen.add(key)
            output = root / f"{key[0]}_t{key[1]}_s{key[2]}"
            if Path(row["output_dir"]) != output:
                raise ValueError("episode output differs from the explicit shard plan")
            result_path = output / "result.json"
            result = row["result"]
            if result_path.exists():
                if json.loads(read(result_path)) != result:
                    raise ValueError(f"ledger/result mismatch: {result_path}")
            else:
                missing.append(str(result_path))
            category = result.get("termination_category", "startup_error")
            if category not in categories:
                raise ValueError(f"unknown mutually exclusive terminal category: {category}")
            choices_path = output / "choices.jsonl"
            if choices_path.exists():
                for step, choice_line in enumerate(read(choices_path).splitlines()):
                    choice = json.loads(choice_line)
                    requests.append({
                        "episode": episode, "step": step,
                        "source": str(choices_path), "request": choice["request"],
                        "prompt_tokens": choice["prompt_tokens"],
                        "source_hashes": result.get("source_hashes", {}),
                        "purpose": "development_memory_only_never_training",
                    })
            elif category != "startup_error":
                missing.append(str(choices_path))
            by_suite[key[0]][category] += 1
            by_task[(key[0], key[1])]["attempted"] += 1
            for name in ("official_success", "correct_finish"):
                value = bool(result.get(name))
                by_suite[key[0]][name] += value
                by_task[(key[0], key[1])][name] += value
            episodes.append({"episode": episode, "output": str(output), "result": result})

    counts = Counter(e["result"].get("termination_category", "startup_error") for e in episodes)
    correct = sum(bool(e["result"].get("correct_finish")) for e in episodes)
    physical = sum(bool(e["result"].get("official_success")) for e in episodes)
    complete = len(seen) == 200 and not missing and not counts["startup_error"]
    summary = {
        "purpose": "original_expert_development_gate_not_model_or_training_results",
        "plan": str(args.plan), "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        "array_job": args.array_job, "planned": 200, "attempted": len(episodes),
        "complete_protocol": complete, "missing": missing,
        "unattempted": [list(k) for k in sorted(expected - seen)],
        "physical_success": physical, "correct_finish": correct,
        "gate_pass": complete and correct >= 160,
        "terminal_counts": dict(counts),
        "by_suite": {suite: dict(values) for suite, values in sorted(by_suite.items())},
        "by_task": [
            {"suite": key[0], "task": key[1], **dict(values),
             "eligible_for_original_training_collection": values["attempted"] == 5 and values["correct_finish"] >= 4}
            for key, values in sorted(by_task.items())
        ],
        "episodes": episodes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output_dir / "sources.json").write_text(json.dumps({"sources": sources}, indent=2) + "\n")
    ranked = sorted(requests, key=lambda r: r["prompt_tokens"], reverse=True)
    for name, selected in (("longest128.jsonl", ranked[:128]),
                           ("over2048.jsonl", [r for r in ranked if r["prompt_tokens"] > 2048])):
        (args.output_dir / name).write_text("".join(json.dumps(row) + "\n" for row in selected))
    print(json.dumps({key: value for key, value in summary.items() if key != "episodes"}, indent=2))


if __name__ == "__main__":
    main()
