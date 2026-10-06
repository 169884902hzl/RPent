# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Summarize only explicit closed moka selection and confirmation ledgers."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def identity(path):
    return {"path": str(path.resolve(strict=True)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def hold_failure(row):
    if row["true_sustained_grasp"] is True:
        return "sustained_grasp_success"
    if row["true_sustained_grasp"] is None:
        return "unknown_sustained_truth"
    checks = row.get("sustained_hold", {}).get("truth", {}).get("checks", [])
    if not checks:
        return "missing_hold_checks"
    if not any(check["finger_contact"] for check in checks):
        return "no_target_finger_support_during_posttrial_hold"
    if all(check["finger_contact"] for check in checks) and any(check["clearance_m"] < .03 for check in checks):
        return "held_target_collision_clearance_below_3cm"
    if not all(check["finger_contact"] for check in checks):
        return "target_finger_support_not_sustained"
    if any(check["touching_original_support"] for check in checks):
        return "original_support_contact_persists"
    return "other_preserved_hold_truth_failure"


def subtask_failure(row, target):
    if target is True:
        return "official_on_subtask_satisfied"
    if target is None:
        return "official_subtask_truth_unknown"
    phase = row.get("private_grasp_phase", {})
    samples = phase.get("samples", [])
    if not samples:
        return "no_recorded_control_contact_samples"
    if not phase["true_sustained_grasp_during_skill"]:
        if not any(sample["finger_contact"] for sample in samples):
            return "no_target_finger_contact"
        reference = phase["reference"]["lower_extent_m"]
        if max(sample["lower_extent_m"] - reference for sample in samples) < .03:
            return "target_contact_without_3cm_clearance"
        return "lift_without_0p5s_sustained_hold"
    return "sustained_grasp_without_on_target_success"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grasp-ledger", type=Path, action="append", required=True)
    parser.add_argument("--subtask-ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records, inputs = [], []
    for kind, paths in (("grasp", args.grasp_ledger), ("subtask", args.subtask_ledger)):
        for path in paths:
            descriptor = identity(path)
            inputs.append(descriptor)
            for number, line in enumerate(path.read_text().splitlines(), 1):
                row = json.loads(line)
                if "moka" not in row["case"]["name"]:
                    continue
                case = row["case"]
                reference = {**descriptor, "line": number}
                cohort = path.parent.parent.name
                receipt = row.get("first_receipt", {}) if kind == "grasp" else row["first_attempt"]["receipt"]
                if kind == "grasp":
                    sustained = row.get("true_sustained_grasp")
                    target = None
                    during, end = None, sustained
                    failure = hold_failure(row)
                    prompt = row.get("contact_prompt")
                    approach = receipt.get("diagnostic_approach")
                    status = row["result"].get("status")
                    official_done = None
                else:
                    phase = row.get("private_grasp_phase", {})
                    during, end = phase.get("true_sustained_grasp_during_skill"), phase.get("true_sustained_grasp_at_end")
                    sustained = during
                    status = row["status"]
                    private = row.get("private_original_task_status", {})
                    labels = [flag for goal, flag in zip(private.get("goals", []), private.get("satisfied", []))
                              if len(goal) >= 2 and goal[0].lower() == "on" and goal[1] == case["object_symbol"]]
                    target = labels[0] if len(labels) == 1 else None
                    official_done = private.get("done")
                    failure = subtask_failure(row, target)
                    prompt = receipt.get("subtask_prompt")
                    approach = "measured_handle_10cm" if case["condition"] == "handle_full_subtask160" else "measured_bounds_centre_10cm"
                records.append({"cohort": cohort, "kind": kind, "condition": case["condition"],
                    "case": case["name"], "episode": case["episode"], "state_sha256": case.get("state_sha256"),
                    "input": reference, "status": status, "executed": receipt.get("executed"),
                    "public_prompt": prompt, "actual_approach": approach, "chunks": receipt.get("chunks"),
                    "public_stop": receipt.get("stop"), "failure_reason": receipt.get("failure_reason"),
                    "sustained_grasp_metric": sustained, "sustained_during_complete_subtask": during,
                    "sustained_at_end": end, "official_on_subtask_success": target,
                    "official_complete_original_task_done": official_done,
                    "diagnostic_failure_type": failure,
                    "visual_verdict": row.get("visual_verified") if kind == "grasp" else receipt.get("place_verified"),
                    "original_labels_unchanged": True})
    groups = []
    for cohort, condition in sorted({(r["cohort"], r["condition"]) for r in records}):
        selected = [r for r in records if (r["cohort"], r["condition"]) == (cohort, condition)]
        known = [r for r in selected if r["sustained_grasp_metric"] is not None]
        target_known = [r for r in selected if r["official_on_subtask_success"] is not None]
        unique = {(r["episode"]["suite"], r["episode"]["task"], r["episode"]["seed"]) for r in selected}
        groups.append({"cohort": cohort, "condition": condition, "requests": len(selected),
            "unique_official_init_indices": len(unique), "correlated_repeat_requests": len(selected) - len(unique),
            "sustained_grasp_successes": sum(r["sustained_grasp_metric"] is True for r in selected),
            "known_sustained_denominator": len(known),
            "sustained_success_rate_on_all_requests": sum(r["sustained_grasp_metric"] is True for r in selected) / len(selected),
            "sustained_during_complete_subtask": dict(Counter(str(r["sustained_during_complete_subtask"]) for r in selected)),
            "sustained_at_end": dict(Counter(str(r["sustained_at_end"]) for r in selected)),
            "official_on_subtask_successes": sum(r["official_on_subtask_success"] is True for r in selected) if target_known else None,
            "official_on_subtask_denominator": len(target_known),
            "official_complete_original_task_done": dict(Counter(str(r["official_complete_original_task_done"]) for r in selected)),
            "actual_public_prompts": dict(Counter(r["public_prompt"] for r in selected)),
            "actual_approaches": dict(Counter(r["actual_approach"] for r in selected)),
            "failure_types": dict(Counter(r["diagnostic_failure_type"] for r in selected)),
            "statuses": dict(Counter(r["status"] for r in selected)),
            "public_stops": dict(Counter(r["public_stop"] for r in selected)),
            "public_failure_reasons": dict(Counter(str(r["failure_reason"]) for r in selected))})
    selection = [g for g in groups if g["cohort"] in ("full_job3620", "exploration_job3670")]
    report = {"producer": identity(Path(__file__)), "inputs": inputs, "moka_records": len(records),
        "groups": groups, "distinct_observed_selection_methods": len(selection),
        "all_five_selection_methods_below_90_percent": len(selection) == 5 and all(
            g["sustained_success_rate_on_all_requests"] < .9 for g in selection),
        "method_count_policy": "3620 reset-short, overhead-centre-short, measured-handle-short and 3670 overhead-centre-complete-transfer, measured-handle-complete-transfer are distinct approach/prompt/stop sequences. Budget changes, B/BA alias names, the existing reset320 confirmation, and unexecuted new300 are not extra methods.",
        "qualification": False, "new_training_rows": 0, "new_physics_trials": 0,
        "limits": ["Selection cohorts each repeat 50 official init indices twice; they do not replace independent confirmation.",
            "Complete transfer uses the On subpredicate from the original task; original turn-on-and-transfer task done is separately preserved.",
            "Grasp-only ledgers did not measure official full-subtask success; unknown is not a failed subtask.",
            "Sustained-during-subtask and posttrial/final sustained hold have different time scopes and are separately named.",
            "The approximate five-method stop is supported as a method-count observation, not five independent causal experiments."]}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "inputs"}, indent=2))


if __name__ == "__main__":
    main()
