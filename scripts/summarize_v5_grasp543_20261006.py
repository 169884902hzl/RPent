# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Summarize SOURCE543 grasp runs from pinned manifests and explicit ledgers.

Pass ledger flags in actual run order. Episodes and infrastructure attempts
from one part share a directory; their attempt_index orders that part's
invocations. Later physical executions are reported as development only.
No simulator, checkpoint, artifact-directory search, or label recomputation
is performed.
"""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

INFRASTRUCTURE_MARKERS = (
    "RpcError", "TimeoutError", "ConnectionError", "ConnectionRefusedError",
    "BrokenPipeError", "RemoteDisconnected", "env_meta mismatch",
    "wait / client connect failed", "daemon exited", "server exited",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ratio(count, denominator):
    return count / denominator if denominator else None


def boolean(value):
    return value if isinstance(value, bool) else None


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    proportion = successes / trials
    scale = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / scale
    radius = z * math.sqrt(proportion * (1 - proportion) / trials
                           + z * z / (4 * trials * trials)) / scale
    return [centre - radius, centre + radius]


def bounded_metric(successes, known, denominator):
    """Leave unknown outcomes unlabelled while reporting both possible bounds."""
    return {"successes": successes, "known": known,
            "unknown_or_not_yet_physical": denominator - known,
            "denominator": denominator, "known_rate": ratio(successes, known),
            "worst_case_rate": ratio(successes, denominator),
            "best_case_rate": ratio(successes + denominator - known, denominator),
            "known_wilson_95CI_descriptive": wilson(successes, known)}


def infrastructure_failure(row):
    receipt = row.get("first_receipt") or {}
    messages = [row.get("raised_error", ""), receipt.get("error", "")]
    messages.extend(item.get("error", "")
                    for item in row.get("private_phase_snapshot_errors", []))
    return bool(row.get("infrastructure_error") or row.get("infrastructure_failure")
                or row.get("failure_classification") == "infrastructure_failure"
                or row.get("status") == "infrastructure_error"
                or any(isinstance(message, str) and any(marker in message
                       for marker in INFRASTRUCTURE_MARKERS) for message in messages))


def physically_executed(row):
    """An unavailable private outcome does not erase observed public motion."""
    receipts = [row.get("first_receipt") or {},
                row.get("public_receipt_before_private_metrology") or {}]
    return bool(row.get("physical_execution_observed")
                or row.get("physical_execution_before_infrastructure_failure")
                or (row.get("executed_vla_actions") or 0) > 0
                or (row.get("executed_public_motion_actions") or 0) > 0
                or any(receipt.get("executed") is True for receipt in receipts)
                or row.get("contact_samples")
                or (row.get("rpent_pick_result") or {}).get("chunks_used", 0) > 0)


def public_receipt(row):
    """Prefer the delivered final receipt, preserving a completed pre-fault one."""
    final = row.get("first_receipt") or {}
    saved = row.get("public_receipt_before_private_metrology") or {}
    if "grasp_verified" in final:
        return final, "first_receipt", boolean(final["grasp_verified"])
    if "grasp_verified" in saved:
        return saved, "public_receipt_before_private_metrology", boolean(saved["grasp_verified"])
    return final or saved, "verdict_unavailable", None


def official_on_success(row):
    """The official On predicate is separate from grasp and original-task done."""
    status = row.get("private_original_task_status_after") or {}
    case = row["case"]
    targets = {goal[1] for goal in case.get("private_original_goal_predicates", [])
               if len(goal) >= 2 and goal[0].lower() == "on"}
    flags = [flag for goal, flag in zip(status.get("goals", []), status.get("satisfied", []))
             if len(goal) >= 2 and goal[0].lower() == "on" and goal[1] in targets]
    return boolean(flags[0]) if len(flags) == 1 else None


def hold_failure_type(row):
    """Describe preserved truth/checks without creating a replacement label."""
    truth = boolean(row.get("true_sustained_grasp"))
    if truth is None:
        return "unknown_posttrial_sustained_truth"
    if truth:
        return "posttrial_sustained_grasp_success"
    checks = (row.get("sustained_hold") or {}).get("truth", {}).get("checks", [])
    if not checks:
        return "preserved_failure_without_hold_checks"
    if not any(check.get("finger_contact") is True for check in checks):
        return "no_target_finger_support_during_posttrial_hold"
    if any(check.get("touching_original_support") is True for check in checks):
        return "original_support_contact_persists"
    if not all(check.get("finger_contact") is True for check in checks):
        return "target_finger_support_not_sustained"
    if any(check.get("clearance_m") is not None and check["clearance_m"] < .03 for check in checks):
        return "held_target_collision_clearance_below_3cm"
    return "other_preserved_hold_truth_failure"


def normalized_attempt(row, references):
    receipt, receipt_source, verdict = public_receipt(row)
    phase = row.get("private_grasp_phase") or {}
    after = row.get("private_original_task_status_after") or {}
    truth = boolean(row.get("true_sustained_grasp"))
    return {"case": row["case"]["name"], "condition": row["case"]["condition"],
            "group": row["case"]["group"], "state_sha256": row["case"]["state_sha256"],
            "episode": row["case"]["episode"], "attempt_index": row.get("attempt_index", 0),
            "output_dir": row.get("output_dir"), "sources": references,
            "physically_executed": physically_executed(row),
            "infrastructure_failure": infrastructure_failure(row),
            "case_had_infrastructure_failure": bool(row.get("case_had_infrastructure_failure")),
            "instrument_fault_after_execution": bool(row.get("instrument_fault_after_execution")),
            "runtime_eligible_physical_result": row.get("eligible_physical_result"),
            "sustained_posttrial_grasp": truth, "public_grasp_verdict": verdict,
            "public_receipt_source": receipt_source,
            "final_receipt_present": bool(row.get("first_receipt")),
            "saved_public_receipt_present": bool(row.get("public_receipt_before_private_metrology")),
            "raw_exported_visual_verified": row.get("visual_verified"),
            "sustained_during_complete_subtask": boolean(phase.get("true_sustained_grasp_during_skill")),
            "sustained_at_end_of_complete_subtask": boolean(phase.get("true_sustained_grasp_at_end")),
            "official_on_subtask_success": official_on_success(row),
            "official_original_task_done": boolean(after.get("done")),
            "exported_official_subtask_success": boolean(row.get("official_subtask_success")),
            "public_prompt": row.get("contact_prompt", receipt.get("subtask_prompt")),
            "original_public_instruction": row["case"].get("instruction"),
            "public_prompt_origin": row.get("full_prompt_origin"),
            "execution_kind": receipt.get("execution_kind"),
            "contact_max_chunks": row.get("contact_max_chunks"),
            "actual_approach": receipt.get("diagnostic_approach"),
            "approach_measurement": row.get("contact_approach_measurement"),
            "public_stop": receipt.get("stop"), "stop_condition": receipt.get("stop_condition"),
            "failure_reason": receipt.get("failure_reason"),
            "diagnostic_failure_type": hold_failure_type(row),
            "verification": receipt.get("verification"), "error_stage": row.get("error_stage"),
            "raised_error": row.get("raised_error"),
            "status": (row.get("result") or {}).get("status", row.get("status")),
            "chunks": receipt.get("chunks", row.get("chunks")),
            "executed_vla_actions": row.get("executed_vla_actions"),
            "executed_public_motion_actions": row.get("executed_public_motion_actions")}


def value_counts(rows, key):
    return dict(Counter(json.dumps(row.get(key), ensure_ascii=False, sort_keys=True) for row in rows))


def cohort_role(cohort):
    if "selection" in cohort or "correlated" in cohort:
        return "selection"
    if "confirmation" in cohort or "independent" in cohort:
        return "confirmation"
    return "diagnostic"


def metrics(cases, rows):
    planned, observed = len(cases), len(rows)
    truths = [row["sustained_posttrial_grasp"] for row in rows]
    known_truth = sum(truth is not None for truth in truths)
    matrix = Counter(dict.fromkeys(("tp", "tn", "fp", "fn"), 0))
    for row in rows:
        truth, verdict = row["sustained_posttrial_grasp"], row["public_grasp_verdict"]
        if truth is not None and verdict is not None:
            matrix["tp" if truth and verdict else "fn" if truth else "fp" if verdict else "tn"] += 1
    paired = sum(matrix.values())
    state_hashes = {case["state_sha256"] for case in cases}
    observed_hashes = {row["state_sha256"] for row in rows}
    roles = sorted({case["analysis_role"] for case in cases})
    physical = bounded_metric(sum(truth is True for truth in truths), known_truth, planned)
    agreement = bounded_metric(matrix["tp"] + matrix["tn"], paired, planned)
    complete_physics = planned > 0 and observed == planned
    distinct_confirmation = roles == ["confirmation"] and len(state_hashes) == planned
    numeric = None
    if complete_physics and distinct_confirmation and observed >= 100:
        numeric = ("supported_by_worst_case_bounds" if physical["worst_case_rate"] >= .9
                   and agreement["worst_case_rate"] >= .95 else
                   "below_threshold_even_at_best_case" if physical["best_case_rate"] < .9
                   or agreement["best_case_rate"] < .95 else "unresolved_with_unknown_outcomes")
    return {"planned": planned, "first_physical_attempts": observed,
            "not_yet_physically_attempted": planned - observed,
            "analysis_roles": roles, "planned_unique_state_sha256": len(state_hashes),
            "observed_unique_state_sha256": len(observed_hashes),
            "planned_correlated_repeat_requests": planned - len(state_hashes),
            "observed_correlated_repeat_requests": observed - len(observed_hashes),
            "first_physical_complete": complete_physics,
            "distinct_registered_confirmation_states": distinct_confirmation,
            "truth_coverage": {"known": known_truth, "unknown_after_physics": observed - known_truth,
                               "rate_over_first_physical": ratio(known_truth, observed)},
            "public_verdict_coverage": {"known": sum(row["public_grasp_verdict"] is not None for row in rows),
                                        "unmeasured_after_physics": sum(row["public_grasp_verdict"] is None for row in rows),
                                        "final_receipts": sum(row["final_receipt_present"] for row in rows),
                                        "saved_pre_metrology_receipts_used": sum(row["public_receipt_source"] == "public_receipt_before_private_metrology" for row in rows)},
            "confusion": dict(matrix), "paired_truth_and_public_verdict": paired,
            "known_truth_public_unmeasured": sum(row["sustained_posttrial_grasp"] is not None
                                                 and row["public_grasp_verdict"] is None for row in rows),
            "physical_success": physical, "verifier_agreement": agreement,
            "false_positive_rate": ratio(matrix["fp"], matrix["fp"] + matrix["tn"]),
            "false_negative_rate": ratio(matrix["fn"], matrix["fn"] + matrix["tp"]),
            "single_class_threshold_evidence": numeric,
            "official_on_subtask": bounded_metric(sum(row["official_on_subtask_success"] is True for row in rows),
                                                   sum(row["official_on_subtask_success"] is not None for row in rows), planned),
            "official_original_task_done": bounded_metric(sum(row["official_original_task_done"] is True for row in rows),
                                                           sum(row["official_original_task_done"] is not None for row in rows), planned),
            "sustained_during_complete_subtask": value_counts(rows, "sustained_during_complete_subtask"),
            "sustained_at_end_of_complete_subtask": value_counts(rows, "sustained_at_end_of_complete_subtask"),
            "actual_public_prompts": value_counts(rows, "public_prompt"),
            "actual_approaches": value_counts(rows, "actual_approach"),
            "public_stops": value_counts(rows, "public_stop"),
            "failure_reasons": value_counts(rows, "failure_reason"),
            "diagnostic_failure_types": value_counts(rows, "diagnostic_failure_type"),
            "statuses": value_counts(rows, "status"),
            "unknown_truth_error_stages": value_counts([row for row in rows
                                                       if row["sustained_posttrial_grasp"] is None], "error_stage")}


def infrastructure_metrics(planned, attempts, case_events, evaluate_limit=True):
    names = {case["name"] for case in planned}
    selected = [attempt for attempt in attempts if attempt["case"] in names]
    faults = {attempt["case"] for attempt in selected if attempt["infrastructure_failure"]
              or attempt["case_had_infrastructure_failure"]}
    events = [event for event in case_events if event["case"] in names]
    faults.update(event["case"] for event in events if event["infrastructure_failure"])
    latest = {attempt["case"]: attempt for attempt in selected}
    unresolved = {name for name in faults if name not in latest or latest[name]["infrastructure_failure"]}
    return {"planned_cases": len(names), "observed_invocations": len(selected),
            "initial_invocations": sum(attempt["attempt_index"] == 0 for attempt in selected),
            "retry_invocations": sum(attempt["attempt_index"] > 0 for attempt in selected),
            "infrastructure_failed_invocations": sum(attempt["infrastructure_failure"] for attempt in selected),
            "postphysical_infrastructure_failed_invocations": sum(attempt["infrastructure_failure"]
                                                                   and attempt["physically_executed"] for attempt in selected),
            "unique_affected_cases": len(faults), "affected_case_names": sorted(faults),
            "rate_over_all_registered_cases": ratio(len(faults), len(names)),
            "registered_limit": .02 if evaluate_limit else None,
            "above_registered_limit": len(faults) > .02 * len(names) if evaluate_limit else None,
            "limit_scope": "whole_manifest_only; condition/group rates are descriptive",
            "recovered_cases": sorted(faults - unresolved), "unresolved_cases": sorted(unresolved),
            "explicit_shared_case_events": len(events),
            "fault_or_policy": "once faulty remains faulty after recovery; unique cases / complete manifest, not shard or invocation count"}


def summarize(manifest_paths, expected_manifest_shas, ledger_sources):
    """Return a report and reviewable attempt roles without opening references."""
    if len(manifest_paths) != len(expected_manifest_shas):
        raise ValueError("supply one --manifest-sha256 for each --manifest, in the same order")
    planned, manifests, manifest_by_case, manifest_sizes = {}, [], {}, {}
    for path, expected in zip(map(Path, manifest_paths), expected_manifest_shas):
        digest = sha(path)
        if digest != expected:
            raise ValueError("manifest SHA mismatch: " + str(path))
        plan = json.loads(path.read_text())
        role = cohort_role(plan.get("cohort", ""))
        manifests.append({"path": str(path.resolve()), "sha256": digest,
                          "cohort": plan.get("cohort"), "analysis_role": role,
                          "conditions": plan["conditions"], "truth_protocol": plan.get("truth_protocol"),
                          "declared_confirmation_audit": plan.get("confirmation_audit"),
                          "declared_explicit_state_exclusions": plan.get("explicit_state_exclusions")})
        manifest_sizes[digest] = len(plan["cases"])
        for case in plan["cases"]:
            name = case["name"]
            if name in planned or case["condition"] not in plan["conditions"]:
                raise ValueError("duplicated or unregistered manifest case: " + name)
            if case["episode"]["suite"] != "libero_90" or not case.get("state_sha256"):
                raise ValueError("SOURCE543 requires registered original LIBERO90 states")
            planned[name] = {**case, "analysis_role": role}
            manifest_by_case[name] = digest

    inputs, missing, attempts, events, run_order = [], [], {}, [], {}
    seen_paths = set()
    for source_index, (kind, raw_path) in enumerate(ledger_sources):
        path = Path(raw_path).expanduser().resolve()
        if path in seen_paths:
            raise ValueError("duplicate explicit ledger path: " + str(path))
        seen_paths.add(path)
        if not path.is_file():
            missing.append({"kind": kind, "path": str(path)})
            continue
        descriptor = {"kind": kind, "path": str(path), "sha256": sha(path),
                      "explicit_source_order": source_index}
        inputs.append(descriptor)
        run_order.setdefault(str(path.parent), source_index)
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            reference = {**descriptor, "line": line_number}
            if isinstance(row.get("case"), str):
                name = row["case"]
                if (kind != "infrastructure" or name not in planned
                        or row.get("manifest_sha256") != manifest_by_case[name]
                        or row.get("planned_cases") != manifest_sizes[manifest_by_case[name]]):
                    raise ValueError("unregistered shared infrastructure event")
                events.append({**row, "source": reference})
                continue
            case = row["case"]
            name = case["name"]
            registered = planned.get(name)
            if registered is None or case != {key: value for key, value in registered.items()
                                              if key != "analysis_role"}:
                raise ValueError("changed or unregistered attempt: " + name)
            index = row.get("attempt_index", 0)
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise ValueError("invalid attempt index: " + name)
            if row.get("registered_state_sha256", case["state_sha256"]) != case["state_sha256"]:
                raise ValueError("attempt changed registered state: " + name)
            invocation_dir = str(Path(row["output_dir"]).parent) if row.get("output_dir") else str(path.parent)
            run_order[invocation_dir] = min(run_order.get(invocation_dir, source_index), source_index)
            key = (name, invocation_dir, index)
            if key in attempts:
                if attempts[key]["row"] != row:
                    raise ValueError("contradictory duplicate invocation: " + name)
                attempts[key]["references"].append(reference)
            else:
                attempts[key] = {"row": row, "references": [reference], "run": invocation_dir,
                                 "line_order": line_number, "source_order": source_index}

    ordered = sorted(attempts.values(), key=lambda item: (
        run_order[item["run"]], item["row"].get("attempt_index", 0),
        item["source_order"], item["line_order"]))
    first, normalized, per_case, violations = {}, [], defaultdict(list), []
    for item in ordered:
        row = normalized_attempt(item["row"], item["references"])
        name = row["case"]
        previous = per_case[name]
        row["explicit_invocation_order"] = len(normalized)
        if row["physically_executed"]:
            row["role"] = "development_physical_repeat" if name in first else "first_physical_attempt"
            if name in first:
                violations.append({"case": name, "reason": "physical_reexecution_after_first_physical_attempt",
                                   "sources": row["sources"]})
            else:
                first[name] = row
        else:
            row["role"] = "zero_physics_infrastructure" if row["infrastructure_failure"] else "zero_physics_outcome"
        if row["attempt_index"] > 0:
            if (row["attempt_index"] != 1 or not previous
                    or previous[-1]["physically_executed"] or not previous[-1]["infrastructure_failure"]):
                violations.append({"case": name, "reason": "retry_not_single_retry_of_prephysics_infrastructure",
                                   "sources": row["sources"]})
        elif previous and name not in first and not previous[-1]["infrastructure_failure"]:
            violations.append({"case": name, "reason": "reexecution_after_non_infrastructure_outcome",
                               "sources": row["sources"]})
        previous.append(row)
        normalized.append(row)

    first_rows = list(first.values())
    groups = {}
    for digest, condition, group in sorted({(manifest_by_case[name], case["condition"], case["group"])
                                           for name, case in planned.items()}):
        cases = [case for name, case in planned.items() if manifest_by_case[name] == digest
                 and case["condition"] == condition and case["group"] == group]
        names = {case["name"] for case in cases}
        group_rows = [row for row in first_rows if row["case"] in names]
        groups[f"{digest[:12]}/{condition}/{group}"] = {
            **metrics(cases, group_rows), "manifest_sha256": digest,
            "condition": condition, "group": group,
            "observed_case_invocations": sum(row["case"] in names for row in normalized),
            "infrastructure": infrastructure_metrics(cases, normalized, events, evaluate_limit=False)}
    infra_by_manifest = {digest: infrastructure_metrics(
        [case for name, case in planned.items() if manifest_by_case[name] == digest], normalized, events)
        for digest in manifest_sizes}
    report = {"scope": "SOURCE543 explicit-ledger monitoring; pan confirmation and moka selection stay separate",
              "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
              "python": sys.executable, "manifests": manifests, "ledger_inputs": inputs,
              "missing_explicit_ledgers": missing, "by_manifest_condition_group": groups,
              "planned": len(planned), "observed_invocations": len(normalized),
              "first_physical_attempts": len(first_rows),
              "missing_first_physical_cases": sorted(planned.keys() - first.keys()),
              "complete_first_physical": bool(planned) and len(first) == len(planned),
              "infrastructure_by_manifest": infra_by_manifest,
              "retry_policy_violations": violations,
              "first_physical_policy": "explicit run order then attempt_index; postphysics instrument failures retained; later physical outcomes never replace the first",
              "unknown_policy": "unknown truth and unmeasured public verdicts remain null; excluded from TP/TN/FP/FN, with worst/best bounds over every registered case",
              "wilson_scope": "descriptive intervals over known labels only; correlated state repeats disclosed; no Wilson lower-bound admission gate",
              "public_verdict_policy": "actual receipt grasp_verified only; completed pre-metrology receipt is preserved; raw exported false cannot stand in for a missing receipt",
              "subtask_policy": "official On, original-task done, sustained-during, final hold and posttrial sustained grasp have separate fields; instant contacts do not establish a sustained-during label",
              "user_grasp_thresholds": {"first_physical_per_class": 100,
                                        "class_physical_success": .9, "verifier_agreement": .95,
                                        "six_class_overall_physical_success": .95},
              "full_six_class_qualification": "not_evaluated",
              "qualification_authorized": False, "behavior_freeze_authorized": False,
              "external_state_or_source_consistency_audit_performed": False,
              "truth_labels_recomputed": False, "new_physical_trials": 0, "new_training_rows": 0}
    return report, first_rows, normalized


class LedgerAction(argparse.Action):
    """Preserve interleaved ledger flags so callers declare actual run order."""

    def __call__(self, parser, namespace, values, option_string=None):
        sources = getattr(namespace, "ledger_sources", None)
        if sources is None:
            sources = []
            namespace.ledger_sources = sources
        sources.append(("infrastructure" if option_string == "--infrastructure-ledger" else "episodes", values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--manifest-sha256", action="append", required=True)
    parser.add_argument("--ledger", type=Path, action=LedgerAction,
                        help="Explicit episodes ledger; interleave flags in actual run order.")
    parser.add_argument("--infrastructure-ledger", type=Path, action=LedgerAction,
                        help="Explicit infrastructure_attempts or shared infrastructure_cases ledger.")
    parser.add_argument("--output", type=Path, required=True, help="New output directory.")
    args = parser.parse_args()
    report, first, attempts = summarize(args.manifest, args.manifest_sha256,
                                        getattr(args, "ledger_sources", []))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for filename, records in (("first_physical_cases.jsonl", first), ("attempt_roles.jsonl", attempts)):
        (args.output / filename).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records))
    print(json.dumps({"planned": report["planned"], "first_physical_attempts": len(first),
                      "invocations": len(attempts), "complete_first_physical": report["complete_first_physical"],
                      "report_sha256": sha(args.output / "report.json")}))


if __name__ == "__main__":
    main()
