"""Pair explicitly registered development episodes without filling missing runs."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(episode):
    return episode["suite"], episode["task"], episode["seed"]


def indexed(rows, expected):
    result = {}
    for row in rows:
        identity = key(row["episode"])
        if identity in result or identity not in expected:
            raise ValueError("duplicate or unregistered episode: " + repr(identity))
        result[identity] = row
    return result


def normalize(row, *, baseline):
    result = row if baseline else row["result"]
    terminal = result.get("primary_terminal") if baseline else result.get("termination_category")
    infrastructure = (
        terminal in {"startup_error", "infrastructure_error", "model_error", "context_error"}
        or (not baseline and result.get("status") != "completed")
    )
    normalized = {
        "episode": row["episode"], "output_dir": row["output_dir"],
        "official_success": bool(result.get("official_success", False)),
        "explicit_successful_finish": bool(result.get(
            "explicit_successful_finish" if baseline else "correct_finish", False)),
        "terminal": terminal, "infrastructure_failure": infrastructure,
        "wall_s": result.get("wall_s"), "source_hashes": result.get("source_hashes", {}),
        "decisions": result.get("decisions"),
    }
    if not baseline:
        normalized.update(
            rejected_finish_attempts=result.get("rejected_finish_attempts", 0),
            ask_help_attempts=result.get("ask_help_attempts", 0),
            missing_memory_files=result.get("rpent_original_memory", {}).get("missing_files", []),
        )
    return normalized


def receipt_counts(trace):
    counts = Counter()
    selected = Counter()
    previous_skill = {}
    for event in trace:
        receipt = event.get("receipt", {})
        tool = receipt.get("tool")
        selected[tool or "unknown"] += 1
        if receipt.get("error") or receipt.get("verification") == "execution_error":
            counts["execution_error"] += 1
        if receipt.get("failure_reason"):
            counts["failure_reason:" + receipt["failure_reason"]] += 1
        if receipt.get("grasp_verified") is False:
            counts["grasp_not_verified"] += 1
        if receipt.get("place_verified") is False:
            counts["place_not_verified"] += 1
        if tool == "ask_help" and previous_skill.get("grasp_verified") is False:
            counts["help_after_failed_grasp"] += 1
        if tool not in {"ask_help", "finish", "reperceive", "retreat"}:
            previous_skill = receipt
    return {"receipt_events": dict(counts), "tool_selections": dict(selected)}


def counts(rows):
    valid = [row for row in rows if not row["infrastructure_failure"]]
    walls = [row["wall_s"] for row in rows if isinstance(row["wall_s"], (int, float))]
    return {
        "recorded": len(rows), "valid_model_episodes": len(valid),
        "official_success": sum(row["official_success"] for row in rows),
        "explicit_successful_finish": sum(row["explicit_successful_finish"] for row in rows),
        "infrastructure_failures": len(rows) - len(valid),
        "terminal_categories": dict(Counter(row["terminal"] for row in rows)),
        "wall_median_s": statistics.median(walls) if walls else None,
    }


def compare(baseline, treatment, expected):
    old = indexed(baseline, expected)
    new = indexed(treatment, expected)
    old = {k: normalize(v, baseline=True) for k, v in old.items()}
    new = {k: normalize(v, baseline=False) for k, v in new.items()}
    pairs, cells, suite_pairs = [], Counter(), defaultdict(Counter)
    for identity in sorted(old.keys() & new.keys()):
        a, b = old[identity], new[identity]
        valid = not (a["infrastructure_failure"] or b["infrastructure_failure"])
        category = (
            "infrastructure_pair" if not valid else
            "both_success" if a["official_success"] and b["official_success"] else
            "regression" if a["official_success"] else
            "gain" if b["official_success"] else "both_failed"
        )
        cells[category] += 1
        suite_pairs[identity[0]][category] += 1
        pairs.append({"episode": dict(suite=identity[0], task=identity[1], seed=identity[2]),
                      "category": category, "A1_M": a, "A2_M": b,
                      "wall_delta_s": b["wall_s"] - a["wall_s"]
                      if isinstance(a["wall_s"], (int, float)) and isinstance(b["wall_s"], (int, float))
                      else None})
    valid_pairs = sum(cells[c] for c in ("both_success", "gain", "regression", "both_failed"))
    return {
        "planned": len(expected), "complete": old.keys() == new.keys() == expected,
        "A1_M": counts(list(old.values())), "A2_M": counts(list(new.values())),
        "missing_A1_M": sorted(expected - old.keys()), "missing_A2_M": sorted(expected - new.keys()),
        "paired": dict(cells), "valid_pairs": valid_pairs,
        "paired_success_delta_pp": 100 * (cells["gain"] - cells["regression"]) / valid_pairs
        if valid_pairs else None,
        "by_suite": {suite: {
            "A1_M": counts([v for k, v in old.items() if k[0] == suite]),
            "A2_M": counts([v for k, v in new.items() if k[0] == suite]),
            "paired": dict(suite_pairs[suite]),
        } for suite in sorted({k[0] for k in expected})},
        "episodes": pairs,
        "scope": "Development comparison; same stock model service/parameters, different harness and memory delivery. Not a single-factor causal estimate. Missing runs and infrastructure failures remain separate from model failures.",
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("baseline", "ledger", "registration", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads(args.registration.read_text())
    manifest = Path(registration["manifest"])
    if sha(manifest) != registration["manifest_sha256"]:
        raise ValueError("registered cohort changed")
    expected = {key(row) for row in json.loads(manifest.read_text())["episodes"]}
    baseline = json.loads(args.baseline.read_text())
    treatment = [json.loads(line) for line in args.ledger.read_text().splitlines() if line.strip()]
    report = compare(baseline, treatment, expected)
    report["registration"] = registration
    report["inputs"] = [{"path": str(p), "sha256": sha(p)}
                        for p in (args.baseline, args.ledger, args.registration, manifest)]
    report["script_sha256"] = sha(__file__)
    for pair in report["episodes"]:
        trace = Path(pair["A2_M"]["output_dir"]) / "choices.jsonl"
        if trace.exists():
            pair["A2_M"].update(receipt_counts(
                [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]))
            pair["A2_M"]["trace"] = {"path": str(trace), "sha256": sha(trace)}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("complete", "A1_M", "A2_M", "paired", "paired_success_delta_pp")}))


if __name__ == "__main__":
    main()
