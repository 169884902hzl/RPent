#!/usr/bin/env python3
"""Attach raw trace evidence to failures in the explicit expert resume ledger."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slim(row):
    receipt = row.get("receipt", {})
    return {
        "decision": row.get("decision"),
        "selected": row.get("selected"),
        "candidates": row.get("candidates"),
        "receipt": receipt,
        "oracle_annotation": row.get("oracle_annotation"),
        "official_success": row.get("official_success"),
        "robot_measurement": row.get("robot_measurement"),
    }


def diagnose(row):
    trace_path = Path(row["output_dir"]) / "choices.jsonl"
    traces = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    result = row["result"]
    last = traces[-1] if traces else {}
    binding = last.get("oracle_annotation") or {}
    category = result.get("termination_category") or result.get("status")
    tools = Counter((trace.get("receipt") or {}).get("tool", "missing") for trace in traces)
    errors = Counter(str((trace.get("receipt") or {}).get("error")) for trace in traces
                     if (trace.get("receipt") or {}).get("error"))
    verification = Counter((trace.get("receipt") or {}).get("verification", "missing") for trace in traces)
    measured_grasps = Counter(str((trace.get("receipt") or {}).get("grasp_verified"))
                             for trace in traces
                             if (trace.get("receipt") or {}).get("tool") in ("grasp", "regrasp_restage"))
    failed_skills = Counter()
    effects = Counter()
    for trace in traces:
        receipt = trace.get("receipt") or {}
        effects[receipt.get("effect", "missing")] += 1
        if receipt.get("verification") in ("failed", "execution_error") or any(
            receipt.get(field) is False
            for field in ("grasp_verified", "place_verified", "articulate_verified")
        ):
            reason = receipt.get("failure_reason") or receipt.get("stop") or receipt.get("verification")
            failed_skills[f"{receipt.get('tool')}:{reason}"] += 1
    context = (last.get("request") or {}).get("context", "")
    if category == "over_token":
        root_cause = "serializer_over_token"
    elif category == "no_legal_candidate" and binding.get("source_entity") is None:
        root_cause = "source_binding_missing_and_recovery_unavailable"
    elif (category == "no_legal_candidate" and binding.get("goal_kind") in ("on", "in")
          and binding.get("target_entity") is None):
        root_cause = "target_binding_missing_and_recovery_unavailable"
    elif category == "no_legal_candidate":
        root_cause = "requested_skill_and_recovery_unavailable"
    elif category == "budget_exhausted":
        root_cause = "budget_exhausted_requires_trace_analysis"
    else:
        root_cause = "requires_trace_analysis"
    return {
        "episode": row["episode"],
        "output_dir": row["output_dir"],
        "result": {key: result.get(key) for key in (
            "official_success", "status", "termination_category", "termination_detail", "error",
            "decisions", "wall_s", "measured_recovery", "fusion_measurements")},
        "trace": {"path": str(trace_path), "sha256": sha(trace_path), "rows": len(traces)},
        "evidence_category": root_cause,
        "category_scope": "last public binding and runtime receipt evidence; no causal replay",
        "tools": dict(tools),
        "receipt_verification": dict(verification),
        "grasp_verification": dict(measured_grasps),
        "execution_errors": dict(errors),
        "failed_skills": dict(failed_skills),
        "effects": dict(effects),
        "last_entities": [{key: entity.get(key) for key in ("id", "name", "visible", "src", "xyz", "part_of")}
                          for entity in last.get("measurements", [])],
        "last_blocked_rows": [line for line in context.splitlines() if line.startswith("blocked ")],
        "last_steps": [slim(trace) for trace in traces[-5:]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("preserve previous evidence; use a new output")
    summary = json.loads(args.summary.read_text())
    records = [diagnose(row) for row in summary["non_program_failures"]]
    failed_skills = Counter()
    failed_reasons = Counter()
    motion_failure_episodes = 0
    for record in records:
        failed_skills.update(record["failed_skills"])
        reasons = Counter()
        for skill_reason, count in record["failed_skills"].items():
            reasons[skill_reason.split(":", 1)[1]] += count
        failed_reasons.update(reasons)
        motion_failure_episodes += any(reason.endswith("not_reached") for reason in reasons)
    report = {
        "summary": {"path": str(args.summary), "sha256": sha(args.summary)},
        "complete": summary["complete"],
        "original_closed": summary["original_closed"],
        "effective_official_physical_success": summary["effective_official_physical_success"],
        "non_program_failures": len(records),
        "termination_categories": dict(Counter(row["result"]["termination_category"] for row in records)),
        "evidence_categories": dict(Counter(row["evidence_category"] for row in records)),
        "failed_skills": dict(failed_skills),
        "failed_reasons": dict(failed_reasons),
        "non_program_failure_episodes_with_motion_not_reached": motion_failure_episodes,
        "records": records,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    print("SHA256", sha(args.output))


if __name__ == "__main__":
    main()
