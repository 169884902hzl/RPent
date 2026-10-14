"""Pair registered budget-development cohorts with their full-task baselines."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from scripts.summarize_v5_interim80_once_20261008 import (
    annotate, group_report, key, pinned, read_rows, ref,
)


def budget_trace(row):
    """Check public-counter deltas and preserve each skill's actual cost."""
    trace = row["trace"]
    events = read_rows(pinned(trace["choices"])) if trace.get("choices") else []
    skills = defaultdict(Counter)
    macro_failures, violations = [], []
    for event in events:
        receipt = event.get("receipt") or {}
        tool = receipt.get("tool") or event["selected"].partition("(")[0]
        before, after = event.get("execution_budget_before"), event.get("execution_budget_after")
        cost = receipt.get("sim_steps_used")
        skills[tool]["attempts"] += 1
        if not isinstance(cost, int) or cost < 0:
            violations.append({"decision": event["decision"], "reason": "missing_or_negative_public_cost"})
        else:
            skills[tool]["sim_steps"] += cost
            if before and after and after["used_sim_steps"] - before["used_sim_steps"] != cost:
                violations.append({"decision": event["decision"], "reason": "counter_delta_mismatch"})
        if tool in ("vla_task", "vla_subtask") and receipt.get("executed"):
            if not receipt.get("native_terminated") and receipt.get("verification") != "execution_error":
                macro_failures.append({"decision": event["decision"], "tool": tool,
                                       "verification": receipt.get("verification"), "sim_steps": cost})
                if receipt.get("verification") != "task_not_completed":
                    violations.append({"decision": event["decision"], "reason": "incomplete_macro_not_failed"})
        if not event.get("candidate_costs") or not before:
            violations.append({"decision": event["decision"], "reason": "planning_cost_or_budget_missing"})
    result = row["result"]
    steps = sum(item.get("sim_steps", 0) for item in skills.values())
    recorded = result.get("skill_step_consumption")
    if recorded is not None:
        expected = {name: {"attempts": count["attempts"], "sim_steps": count["sim_steps"]}
                    for name, count in skills.items()}
        if recorded != expected:
            violations.append({"reason": "episode_skill_totals_disagree_with_choices",
                               "recorded": recorded, "choices": expected})
    return {"skills": {name: dict(count) for name, count in sorted(skills.items())},
            "decision_sim_steps": steps, "execution_budget": result.get("execution_budget"),
            "budget_end_kind": result.get("budget_end_kind"),
            "macro_incompletion_receipts": macro_failures,
            "accounting_violations": violations,
            "max_prompt_tokens": max((event.get("prompt_tokens", 0) for event in events), default=0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prep", type=Path, required=True)
    parser.add_argument("--cohort-root", type=Path, required=True)
    parser.add_argument("--baseline-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registration = args.prep / "manifest.json"
    index = json.loads(registration.read_text())
    plans = [json.loads(pinned(item).read_text()) for item in index["files"]]
    episodes = [episode for plan in plans for episode in plan["episodes"]]
    expected = {key(episode) for episode in episodes}
    if len(expected) != len(episodes):
        raise ValueError("registered cohort contains duplicate episode identities")
    cohort = plans[0]["cohort"]
    if len(expected) != {"expert": 200, "A3-N": 80}[cohort]:
        raise ValueError("cohort size differs from its registered contract")
    references = [ref(registration), ref(args.baseline_ledger), ref(Path(__file__)),
                  ref(Path(__file__).with_name("summarize_v5_interim80_once_20261008.py"))]
    actual, infrastructure, unresolved_tail = {}, [], []
    for ledger in sorted(args.cohort_root.glob("**/probe/episodes.jsonl")):
        raw = ledger.read_bytes()
        # An appended incomplete line is pending, never a discarded outcome.
        boundary = raw.rfind(b"\n") + 1
        if boundary < len(raw):
            unresolved_tail.append({"path": str(ledger), "bytes": len(raw)-boundary})
        ledger_ref = ref(ledger)
        references.append(ledger_ref)
        for line in raw[:boundary].splitlines():
            row = json.loads(line)
            identity = key(row["episode"])
            if identity not in expected:
                raise ValueError(f"unregistered episode: {identity}")
            annotated = annotate(row, ledger_ref, "public_budget_development")
            if annotated["accounting_group"] == "infrastructure":
                infrastructure.append(annotated)
                continue
            if identity in actual:
                raise ValueError(f"duplicate functional outcome: {identity}")
            annotated["budget_trace"] = budget_trace(annotated)
            actual[identity] = annotated
    baseline = {key(row["episode"]): row for row in read_rows(args.baseline_ledger)}
    if baseline.keys() != expected:
        raise ValueError("baseline does not cover the exact same registered states")
    pairs, flips, matrix = [], [], Counter()
    for episode in episodes:
        identity = key(episode)
        previous = baseline[identity]["result"].get("official_success")
        current = actual.get(identity)
        succeeded = current["result"].get("official_success") if current else None
        pair = {"episode": episode, "baseline_success": previous, "current_success": succeeded,
                "termination_reason": current["result"].get("termination_reason") if current else None,
                "skill_step_consumption": current["budget_trace"]["skills"] if current else None,
                "execution_budget": current["budget_trace"]["execution_budget"] if current else None,
                "trace": current["trace"].get("choices") if current else None}
        pairs.append(pair)
        if isinstance(succeeded, bool):
            matrix[f"baseline_{int(previous)}_current_{int(succeeded)}"] += 1
            if previous != succeeded:
                flips.append(pair)
    aggregate = defaultdict(Counter)
    for row in actual.values():
        for skill, counts in row["budget_trace"]["skills"].items():
            aggregate[skill].update(counts)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for name, rows in (("episodes", list(actual.values())), ("paired", pairs),
                       ("flips", flips), ("infrastructure_attempts", infrastructure)):
        path = output / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        files.append(ref(path))
    report = {"cohort": cohort, "summary": group_report(list(actual.values()), len(expected)),
              "per_suite": {suite: group_report([row for ident, row in actual.items() if ident[0] == suite],
                    sum(e["suite"] == suite for e in episodes)) for suite in sorted({e["suite"] for e in episodes})},
              "paired_result_counts": dict(matrix), "flipped_episodes": len(flips),
              "budget_end_counts": dict(Counter(row["result"].get("budget_end_kind") for row in actual.values()
                                                if row["result"].get("termination_category") == "budget_exhausted")),
              "skill_step_consumption": {name: dict(counts) for name, counts in sorted(aggregate.items())},
              "accounting_violations": sum(len(row["budget_trace"]["accounting_violations"]) for row in actual.values()),
              "infrastructure_attempts": len(infrastructure), "pending_ledger_tails": unresolved_tail,
              "source_commit": index["source_commit"], "references": references, "files": files,
              "confirmation": False, "behavior_frozen": False, "training_allowed": False}
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": ref(output / "manifest.json"), "summary": report["summary"],
                      "budget_end_counts": report["budget_end_counts"],
                      "accounting_violations": report["accounting_violations"]}))


if __name__ == "__main__":
    main()
