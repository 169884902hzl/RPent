"""Summarize explicit A3 development ledgers and pair the registered episodes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from scripts.compare_v5_A2M_A1M_20261003 import counts, key, normalize, receipt_counts
from scripts.summarize_v5_timing40_20261001 import distribution


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pinned(descriptor):
    path = Path(descriptor["path"])
    if sha(path) != descriptor["sha256"]:
        raise ValueError("registered input changed: " + str(path))
    return json.loads(path.read_text())


def measured_timing(event):
    """Resolve recorded latency aliases without treating HTTP as computation."""
    timing = dict(event.get("timing_s", {}))
    kind = timing.get("decision_inference_kind")
    field = {"http_round_trip": "http_round_trip", "server_compute": "model_inference"}.get(kind)
    if field and timing.get(field) is None:
        timing[field] = timing.get("decision_inference")
    return timing


def first_grasp(trace):
    """Keep the first actual grasp receipt, including failed approaches."""
    for event in trace:
        receipt = event.get("receipt", {})
        if receipt.get("tool") not in ("grasp", "regrasp_restage"):
            continue
        return {"mode": receipt.get("mode", receipt["tool"]),
                "verified": receipt.get("grasp_verified") is True,
                "execution_error": receipt.get("verification") == "execution_error",
                "unreached_approach": receipt.get("failure_reason") == "approach_not_reached",
                "unreached_wrist": receipt.get("failure_reason") == "wrist_pose_not_reached",
                "decision": event.get("decision"), "receipt": receipt}
    return None


def paired(left, right):
    """Keep missing and infrastructure episodes outside model comparisons."""
    cells, by_suite, episodes = Counter(), defaultdict(Counter), []
    for identity in sorted(left.keys() & right.keys()):
        a, b = left[identity], right[identity]
        category = (
            "infrastructure_pair" if a["infrastructure_failure"] or b["infrastructure_failure"] else
            "request_failure_pair" if a["request_failure"] or b["request_failure"] else
            "both_success" if a["official_success"] and b["official_success"] else
            "regression" if a["official_success"] else
            "gain" if b["official_success"] else "both_failed"
        )
        cells[category] += 1
        by_suite[identity[0]][category] += 1
        episodes.append({"episode": dict(suite=identity[0], task=identity[1], seed=identity[2]),
                         "category": category,
                         "left_success": a["official_success"], "right_success": b["official_success"]})
    valid = sum(cells[c] for c in ("both_success", "gain", "regression", "both_failed"))
    return {"recorded_pairs": len(episodes), "valid_pairs": valid, "cells": dict(cells),
            "success_delta_pp": 100 * (cells["gain"] - cells["regression"]) / valid if valid else None,
            "missing_left": [list(k) for k in sorted(right.keys() - left.keys())],
            "missing_right": [list(k) for k in sorted(left.keys() - right.keys())],
            "by_suite": {k: dict(v) for k, v in by_suite.items()}, "episodes": episodes}


def summarize_group(group):
    manifest = read_pinned(group["manifest"])
    expected = {key(e) for e in manifest["episodes"]}
    if len(expected) != 40 or len(manifest["episodes"]) != 40:
        raise ValueError("development group must contain its registered 40 episodes")
    raw, sources = [], []
    for descriptor in group["results"]:
        path = Path(descriptor["path"])
        if not path.exists():
            sources.append({**descriptor, "exists": False, "sha256": None})
            continue
        if descriptor.get("sha256") and sha(path) != descriptor["sha256"]:
            raise ValueError("completed baseline changed: " + str(path))
        data = path.read_text()
        raw.extend(json.loads(data) if descriptor["format"] == "json" else
                   [json.loads(line) for line in data.splitlines() if line.strip()])
        sources.append({**descriptor, "exists": True, "sha256": sha(path)})
    indexed, traces = {}, []
    timing, by_suite_timing = defaultdict(list), defaultdict(lambda: defaultdict(list))
    event_totals, selections, timing_kinds = Counter(), Counter(), Counter()
    first_grasp_by_mode = defaultdict(Counter)
    for row in raw:
        identity = key(row["episode"])
        if identity not in expected or identity in indexed:
            raise ValueError("duplicate or unregistered episode: " + repr(identity))
        result = normalize(row, baseline=group.get("baseline", False))
        indexed[identity] = result
        if group.get("baseline", False):
            continue
        trace_path = Path(row["output_dir"]) / "choices.jsonl"
        if not trace_path.exists():
            result["trace_missing"] = True
            continue
        trace = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
        result.update(receipt_counts(trace))
        event_totals.update(result["receipt_events"])
        selections.update(result["tool_selections"])
        result["actual_decisions"] = len(trace)
        result["first_grasp"] = first_grasp(trace)
        if result["first_grasp"] is not None:
            metrics = first_grasp_by_mode[result["first_grasp"]["mode"]]
            metrics["attempts"] += 1
            for field in ("verified", "execution_error", "unreached_approach", "unreached_wrist"):
                metrics[field] += result["first_grasp"][field]
        result["trace"] = {"path": str(trace_path), "sha256": sha(trace_path)}
        sequence = []
        for event in trace:
            measured = measured_timing(event)
            timing_kinds[measured.get("decision_inference_kind", "unrecorded")] += 1
            for field in ("model_inference", "http_round_trip", "decision_inference", "choice_request", "perception", "execution", "total"):
                value = measured.get(field)
                if isinstance(value, (int, float)):
                    timing[field].append(value)
                    by_suite_timing[identity[0]][field].append(value)
            sequence.append({k: event[k] for k in
                             ("decision", "selected", "candidates", "answer", "receipt", "timing_s") if k in event})
        traces.append({"episode": row["episode"], "source": result["trace"], "sequence": sequence})
    model_identity = None
    if group.get("model_identity"):
        path = Path(group["model_identity"])
        if path.exists():
            model_identity = {"path": str(path), "sha256": sha(path), "content": json.loads(path.read_text())}
            if group.get("expected_weight_sha256") and (
                model_identity["content"].get("status") != "ok"
                or model_identity["content"].get("revision") != group["expected_weight_sha256"]
                or model_identity["content"].get("max_context_tokens") != 3072
            ):
                raise ValueError("A3 model identity differs from registration")
    suites = sorted({k[0] for k in expected})
    summary = {**counts(list(indexed.values())), "complete": indexed.keys() == expected,
               "planned": len(expected), "missing": [list(k) for k in sorted(expected - indexed.keys())],
               "model_identity": model_identity, "manifest": group["manifest"], "result_sources": sources,
               "source_scope": group["source_scope"], "memory_scope": group.get("memory_scope", "none"),
               "by_suite": {suite: counts([v for k, v in indexed.items() if k[0] == suite]) for suite in suites},
               "step_timing": {k: distribution(v) for k, v in timing.items()},
               "decision_timing_kinds": dict(timing_kinds),
               "first_grasp_by_mode": {mode: {**dict(values),
                   "rates": {field: values[field] / values["attempts"] for field in
                             ("verified", "execution_error", "unreached_approach", "unreached_wrist")}}
                   for mode, values in first_grasp_by_mode.items()},
               "by_suite_step_timing": {suite: {k: distribution(v) for k, v in values.items()}
                                        for suite, values in by_suite_timing.items()},
               "receipt_events_overlapping": dict(event_totals), "tool_selections": dict(selections),
               "episodes": list(indexed.values()), "decision_sequences": traces}
    return summary, indexed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text())
    summaries, groups = {}, {}
    for name, group in index["groups"].items():
        summaries[name], groups[name] = summarize_group(group)
    comparisons = {name: paired(groups[a], groups[b]) for name, (a, b) in index["comparisons"].items()}
    report = {"purpose": "development_only_not_final_or_single_factor_causal_estimate",
              "groups": summaries, "comparisons": comparisons,
              "index": {"path": str(args.index), "sha256": sha(args.index)},
              "script_sha256": sha(__file__),
              "latency_scope": "model_inference=local server computation; http_round_trip=transport wall; total=per-step harness including perception/execution; episode wall includes startup",
              "failure_scope": "Mutually exclusive recorded terminal categories and overlapping actual receipt events are separate. Budget exhaustion alone does not establish perception or skill root cause.",
              "legal_memory_scope": index.get("legal_memory_scope")}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"groups": {k: {f: v[f] for f in
        ("recorded", "official_success", "complete", "infrastructure_failures", "wall_median_s")}
        for k, v in summaries.items()}, "comparisons": {k: {f: v[f] for f in
        ("recorded_pairs", "cells", "success_delta_pp")} for k, v in comparisons.items()}}))


if __name__ == "__main__":
    main()
