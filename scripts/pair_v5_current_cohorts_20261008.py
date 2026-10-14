"""Pair retained expert and model cohorts by the exact registered identity."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from summarize_v5_interim80_once_20261008 import key, read_rows, ref


def index_rows(rows):
    result = {}
    for row in rows:
        identity = key(row["episode"])
        if identity in result:
            raise ValueError(f"duplicated paired identity: {identity}")
        result[identity] = row
    return result


def trace_evidence(row):
    directory = Path(row.get("output_dir") or row["output"])
    path = directory / "choices.jsonl"
    events = read_rows(path) if path.is_file() else []
    skills, reasons, budgets = Counter(), Counter(), defaultdict(Counter)
    motion = []
    for event in events:
        receipt = event.get("receipt") or {}
        tool = receipt.get("tool") or event.get("selected", "").split("(")[0]
        skills[tool] += 1
        reason = receipt.get("failure_reason") or receipt.get("stop") or receipt.get("verification")
        if receipt.get("verification") in ("failed", "execution_error", "unmeasured"):
            reasons[str(reason)] += 1
        budgets[tool]["decisions"] += 1
        budgets[tool]["chunks"] += max(int(receipt.get("chunks", 0) or 0),
            int((receipt.get("primitive_result") or {}).get("chunks_used", 0) or 0))
        for evidence in event.get("motion_evidence", []):
            budgets[tool]["scripted_steps"] += int(evidence.get("steps_used", 0) or 0)
            if evidence.get("name") in ("move_to", "move_pose"):
                motion.append({"decision": event.get("decision"), "selected": event.get("selected"),
                    "receipt_reason": reason, "evidence": evidence})
    rejected = directory / "rejected_request.json"
    last = events[-1] if events else {}
    return {"choices": ref(path) if path.is_file() else None,
        "skills": dict(skills), "failed_receipt_reasons": dict(reasons),
        "budget_by_skill": {k: dict(v) for k, v in budgets.items()},
        "motion_attempts": motion, "last_binding": last.get("oracle_annotation"),
        "last_receipt": last.get("receipt"),
        "rejected_request": ref(rejected) if rejected.exists() else None,
        "causal_replay_performed": False}


def pair(old, new, label):
    old, new = index_rows(old), index_rows(new)
    if set(old) != set(new):
        raise ValueError(f"identity mismatch in {label}")
    counts, rows = Counter(), []
    for identity in sorted(old):
        a, b = old[identity], new[identity]
        before, after = (r["result"].get("official_success") is True for r in (a, b))
        transition = ("success" if before else "failure") + "_to_" + ("success" if after else "failure")
        counts[transition] += 1
        row = {"episode": {"suite": identity[0], "task": identity[1], "seed": identity[2]},
            "transition": transition, "previous_output": a.get("output_dir") or a.get("output"),
            "current_output": b.get("output_dir") or b.get("output"),
            "current_category": b["result"].get("termination_category"),
            "current_error": b["result"].get("error")}
        if before != after:
            row["current_evidence"] = trace_evidence(b)
        rows.append(row)
    return {"label": label, "denominator": len(rows),
        "previous_successes": sum(r["result"].get("official_success") is True for r in old.values()),
        "current_successes": sum(r["result"].get("official_success") is True for r in new.values()),
        "transitions": dict(counts), "all_pairs": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    a3_path = root / "results/harness_v5/interim574_20261007/accounting80_20261008_r3/once80.jsonl"
    a4_path = root / "artifacts/interim80_A4N_legal_r2_20261008/once80.jsonl"
    expert_path = root / "artifacts/expert_legal_r2_manifest_20261008_remote73_r1/final_expert_legal_r2_200.json"
    history_path = root / "results/harness_v5/placement441_original_gate200_20261004/job3414/summary/summary.json"
    a3, a4 = read_rows(a3_path), read_rows(a4_path)
    expert = json.loads(expert_path.read_text())["effective_rows"]
    old = json.loads(history_path.read_text())["episodes"]
    if len(expert) != 200 or len(a3) != 80 or len(a4) != 80:
        raise ValueError("cohorts are not complete")
    report = {"A3_47_vs_A4_44": pair(a3, a4, "same80 A3-N versus A4-N"),
        "expert_177_vs_171": pair(old, expert, "original200 historical versus current expert"),
        "budget_exhausted_evidence": {
            label: [{"episode": row["episode"], "evidence": trace_evidence(row)} for row in rows
                    if row["result"].get("termination_category") == "budget_exhausted"]
            for label, rows in (("expert", expert), ("A3-N", a3))},
        "scope": "interim evidence, causal hypotheses require replay; not freeze qualification"}
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "paired_and_budget_evidence.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    manifest = {"generator": ref(__file__), "inputs": list(map(ref, (a3_path, a4_path, expert_path, history_path))),
        "outputs": [ref(path)], "training_allowed": False}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: {field: v[field] for field in ("denominator", "previous_successes", "current_successes", "transitions")}
                      for k, v in report.items() if "vs" in k}))
    print(json.dumps(ref(args.output / "manifest.json")))


if __name__ == "__main__":
    main()
