# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Reclassify an explicit complete cohort without modifying its original score."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from robots.libero.v5_termination import classify_v2


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger = [json.loads(line) for line in args.ledger.read_text().splitlines()]
    assert len(ledger) == 40
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for record in ledger:
        result = record["result"]
        root = Path(record["output_dir"])
        source = root / "choices.jsonl"
        trace = [json.loads(line) for line in source.read_text().splitlines()]
        receipts = [step["receipt"] for step in trace]
        tool = trace[-1]["selected"].split("(", 1)[0] if trace else None
        new = classify_v2(result, SimpleNamespace(tool=tool), receipts)
        category, detail = new or (result["termination_category"], result.get("termination_detail"))
        error_actions = Counter(step["selected"] for step in trace if step["receipt"].get("error"))
        errors = Counter(step["receipt"]["tool"] for step in trace if step["receipt"].get("error"))
        flags = {
            "failed_grasp_verifications": sum(r.get("tool") in ("grasp", "regrasp_restage") and r.get("grasp_verified") is False for r in receipts),
            "execution_error_by_tool": dict(errors),
            "repeated_error_actions": {a:n for a,n in error_actions.items() if n>1},
            "verified_place_before_incomplete_whole_goal": sum(step["receipt"].get("place_verified",False) and not step["official_success"] for step in trace),
        }
        rows.append({"episode":record["episode"],"output_dir":str(root),
                     "original_termination_category":result["termination_category"],
                     "new_bookkeeping_category":category,"new_detail":detail,
                     "official_success":bool(result["official_success"]),
                     "native_terminated":bool(result.get("native_terminated")),
                     "correct_finish":bool(result["correct_finish"]),
                     "false_finish":bool(result.get("false_finish")),
                     "flags":flags,"actions":[step["selected"] for step in trace],
                     "last_request":trace[-1]["request"] if trace else None,
                     "last_answer":trace[-1]["answer"] if trace else None,
                     "original_result_sha256":digest(root/"result.json"),
                     "original_choices_sha256":digest(source)})
    report = {"purpose":"new terminal bookkeeping only; original physical and explicit-finish scores unchanged",
              "ledger":str(args.ledger),"ledger_sha256":digest(args.ledger),
              "attempted":len(rows),"correct_finish":sum(r["correct_finish"] for r in rows),
              "physical_success":sum(r["official_success"] for r in rows),
              "new_category_counts":dict(Counter(r["new_bookkeeping_category"] for r in rows)),
              "old_category_counts":dict(Counter(r["original_termination_category"] for r in rows)),
              "native_success_reclassified":sum(r["new_bookkeeping_category"]=="success" and r["original_termination_category"] in ("perception_missing_object","budget_exhausted") for r in rows),
              "execution_errors_by_tool":dict(sum((Counter(r["flags"]["execution_error_by_tool"]) for r in rows),Counter())),
              "classification_limit":"A verified placement with an incomplete whole goal does not prove a false-positive subgoal check. Perception, binding, and placement root causes still need measured evidence or manual review.",
              "episodes":rows}
    (args.output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="episodes"},indent=2))


if __name__ == "__main__":
    main()
