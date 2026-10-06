"""Read explicit SOURCE543 skill ledgers; selection never grants qualification."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

from scripts.summarize_v5_skill501_original import infrastructure_result, ratio, setup_truth, summarize, wilson
from scripts.probe_v5_skill501_original import sha


def capture_ledger(path, destination):
    """Freeze complete appended records; retain an in-flight tail as evidence."""
    path = Path(path).expanduser().resolve()
    record = {"path": str(path), "exists": path.is_file()}
    if not record["exists"]:
        return path, record
    raw = path.read_bytes()
    boundary = raw.rfind(b"\n") + 1
    complete, tail = raw[:boundary], raw[boundary:]
    destination.write_bytes(complete)
    record.update(captured_sha256=hashlib.sha256(raw).hexdigest(), complete_records_sha256=sha(destination),
                  snapshot=str(destination), deferred_tail_bytes=len(tail))
    if tail:
        tail_path = destination.with_suffix(".deferred_tail.bin")
        tail_path.write_bytes(tail)
        record["deferred_tail"] = str(tail_path)
    return destination, record


def runtime_verdict(stage, kind):
    key = "grasp_verified" if kind == "grasp" else "place_verified" if kind in {"place", "grasp_then_subtask"} else "articulate_verified"
    return stage.get("receipt", {}).get(key)


def unmeasured_reasons(stage):
    receipt = stage.get("receipt", {})
    approach = receipt.get("fixture_handle_approach") or stage.get("contact_evidence", {}).get("approach") or {}
    containers = [receipt, receipt.get("articulation_state", {}),
                  stage.get("verification_measurements", {}).get("articulation", {}),
                  stage.get("verification_measurements", {}).get("place", {}),
                  approach.get("before", {}), approach.get("after_wrist_refinement", {})]
    reasons = list(dict.fromkeys(str(item[key]) for item in containers if isinstance(item, dict)
                                for key in ("failure_reason", "reason") if item.get(key)))
    return reasons or ["unmeasured_reason_not_recorded"]


def case_diagnostic(row, condition):
    """Classify recorded evidence, without diagnosing unseen geometry or goals."""
    case = row["case"]
    stage = row.get("first_attempt") or {}
    receipt = stage.get("receipt", {})
    before = stage.get("private_before", {})
    after = stage.get("private_after", {})
    truth = stage.get("private_true_sustained_grasp") if case["kind"] == "grasp" else after.get("satisfied")
    verdict = runtime_verdict(stage, case["kind"])
    executed = stage.get("physically_executed") is True
    infra = infrastructure_result(row)
    reason = receipt.get("failure_reason") or receipt.get("reason")
    budget = receipt.get("stop") == "chunk_budget" and receipt.get("chunks", 0) >= condition["max_chunks"]
    contact = stage.get("contact_evidence", {})
    approach = receipt.get("fixture_handle_approach") or contact.get("approach") or {}
    contact_actions = contact.get("executed_vla_actions")
    contact_executed = contact_actions > 0 if isinstance(contact_actions, int) else None
    if infra:
        category = "infrastructure_unavailable"
    elif row.get("raised_error"):
        category = "development_exception"
    elif not stage:
        category = row["status"]  # Preserve the recorded setup/binding label.
    elif receipt.get("verification") == "execution_error" or receipt.get("error"):
        category = "skill_execution_error"
    elif contact_executed is False and (approach.get("ready_for_contact") is False or
            approach and reason in {"current_fixture_handle_not_measured", "wrist_fixture_handle_not_measured",
                                   "fixture_approach_not_reached", "fixture_approach_interrupted", "handle_views_disagree"}):
        category = "measured_approach_not_ready_contact_not_executed"
    elif not executed:
        category = "first_skill_not_executed"
    elif not isinstance(truth, bool):
        category = "private_truth_unknown"
    elif truth:
        category = "already_satisfied_preserved" if before.get("satisfied") is True else "newly_satisfied" if before.get("satisfied") is False else "success_initial_truth_unknown"
    elif before.get("satisfied") is True:
        category = "already_satisfied_then_regressed"
    elif budget:
        category = "contact_budget_exhausted_without_endpoint"
    else:
        category = "requested_endpoint_not_reached"
    expected_mode = {"turn_on": "turnon", "turn_off": "turnoff"}.get(case["mode"], case["mode"])
    predicates = [value.get("predicate") for value in (before, after)]
    queried_modes = [value[0] if value else None for value in predicates]
    return {"case": case["name"], "kind": case["kind"], "type": case["type"], "method": case["condition"],
            "state_sha256": case["state_sha256"], "episode": case["episode"],
            "status": row["status"], "root_cause_category": category,
            "infrastructure_result": infra, "first_skill_physically_executed": executed,
            "private_truth": truth, "private_before": before.get("satisfied"),
            "runtime_verified": verdict, "runtime_verification": receipt.get("verification"),
            "runtime_verification_rule": receipt.get("verification_rule"),
            "runtime_failure_reason": reason, "runtime_effect": receipt.get("effect"),
            "unmeasured_reasons": unmeasured_reasons(stage) if stage and verdict is None else [],
            "expected_private_mode": expected_mode, "queried_private_modes": queried_modes,
            "private_mode_mismatch": any(mode is not None and mode != expected_mode for mode in queried_modes),
            "private_before_joint_qpos": before.get("joint_qpos"), "private_after_joint_qpos": after.get("joint_qpos"),
            "place_setup_sustained_truth": setup_truth(row),
            "contact_chunks": receipt.get("chunks"), "contact_budget_exhausted": budget,
            "executed_vla_actions": contact_actions, "contact_physically_executed": contact_executed,
            "measured_handle_before": approach.get("before"),
            "measured_handle_wrist": approach.get("after_wrist_refinement"),
            "measured_approach_ready": approach.get("ready_for_contact"),
            "measured_approach_waypoints": approach.get("waypoints", []),
            "wall_s": row.get("case_wall_s", row.get("wall_s")),
            "trace": str(Path(row["output_dir"]) / "choices.jsonl"), "choices_sha256": row.get("choices_sha256"),
            "binding_error": row.get("binding_error"), "raised_error": row.get("raised_error"),
            "classification_scope": "evidence category, not a claim about an unrecorded physical root cause; private joints/predicates are report labels only"}


def placement_scopes(records):
    """Keep preparation quality and endpoint change as separate strata."""
    placements = [record for record in records if record["kind"] == "place"
                  and record["first_skill_physically_executed"] and not record["infrastructure_result"]]
    valid_setup = [record for record in placements if record["place_setup_sustained_truth"] is True]
    populations = {
        "true_setup_endpoint": valid_setup,
        "true_setup_initially_unsatisfied_endpoint": [record for record in valid_setup if record["private_before"] is False],
        "initially_unsatisfied_endpoint_any_setup": [record for record in placements if record["private_before"] is False],
    }
    result = {}
    for name, population in populations.items():
        known = [record for record in population if isinstance(record["private_truth"], bool)]
        successes = sum(record["private_truth"] for record in known)
        result[name] = {"attempted": len(population), "known_truth": len(known),
                        "unknown_truth": len(population) - len(known), "successes": successes,
                        "success_over_known": ratio(successes, len(known)),
                        "wilson_95CI": wilson(successes, len(known)),
                        "already_satisfied_before": sum(record["private_before"] is True for record in population)}
    result["scope"] = "private setup truth is a reported stratum, not a runtime gate; endpoint success includes preservation unless initially-unsatisfied is explicit; no original label or verdict is changed"
    return result


def run_summary(manifest_path, ledger_paths, infrastructure_paths, output, *, source_snapshot=None, source_commit=None, job_ids=()):
    manifest_path = Path(manifest_path).expanduser().resolve()
    plan = json.loads(manifest_path.read_text())
    if plan.get("cohort") != "selection" or plan.get("qualification_authorized") is not False or plan.get("new_training_rows") != 0:
        raise ValueError("explicit selection manifest required; no qualification or training admission")
    manifest_sha = sha(manifest_path)
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    preparation = output / "preparation"
    preparation.mkdir()
    snapshots, infrastructure_snapshots, inputs = [], [], []
    for role, paths, collection in (("ledger", ledger_paths, snapshots),
                                     ("infrastructure", infrastructure_paths, infrastructure_snapshots)):
        for index, path in enumerate(paths):
            snapshot, evidence = capture_ledger(path, preparation / f"{role}_{index:02d}.jsonl")
            collection.append(snapshot)
            inputs.append({"role": role, **evidence})
    report = summarize([manifest_path], snapshots, infrastructure_snapshots)
    if sha(manifest_path) != manifest_sha:
        raise ValueError("registered manifest changed during CPU summary")
    diagnostics = []
    for snapshot in snapshots:
        if snapshot.is_file():
            with snapshot.open() as stream:
                for line in stream:
                    if line.strip():
                        row = json.loads(line)
                        diagnostics.append(case_diagnostic(row, plan["conditions"][row["case"]["condition"]]))
    grouped = defaultdict(list)
    for diagnostic in diagnostics:
        grouped[f"{diagnostic['type']}/{diagnostic['method']}"].append(diagnostic)
    table = []
    for group, metrics in report["by_type_condition"].items():
        records = grouped[group]
        infra = report["infrastructure_by_type_condition"][group]
        row = {"type_method": group, "planned": metrics["planned"], "completed_case_records": metrics["recorded"],
               "pending_case_records": metrics["missing"], "infrastructure_fault_cases": infra["cases_with_recorded_infrastructure_fault"],
               "unresolved_infrastructure_cases": infra["unresolved_infrastructure_cases"],
               "physical_first_attempts": metrics["first_attempt_executed"], "private_known": metrics["known_truth"],
               "contact_vla_executed": sum(record["contact_physically_executed"] is True and not record["infrastructure_result"] for record in records),
               "contact_vla_not_executed": sum(record["contact_physically_executed"] is False and not record["infrastructure_result"] for record in records),
               "contact_vla_execution_unknown": sum(record["contact_physically_executed"] is None and not record["infrastructure_result"] for record in records),
               "private_successes": metrics["true_successes"], "private_success_over_known": metrics["success_over_executed_known"],
               "private_success_over_planned": metrics["success_over_planned"],
               "private_success_wilson_95CI": metrics["wilson_95CI"],
               "private_already_satisfied_before": metrics["counts"].get("predicate_already_satisfied_before_attempt", 0),
               "private_known_initially_unsatisfied": metrics["counts"].get("known_initially_unsatisfied", 0),
               "private_newly_satisfied": metrics["counts"].get("newly_satisfied", 0),
               "private_newly_satisfied_rate": metrics["newly_satisfied_rate"],
               "placement_scopes": placement_scopes(records),
               "runtime_verified_true": sum(record["runtime_verified"] is True and not record["infrastructure_result"] for record in records),
               "runtime_verified_false": sum(record["runtime_verified"] is False and not record["infrastructure_result"] for record in records),
               "runtime_verified_unmeasured": sum(record["runtime_verified"] is None and record["first_skill_physically_executed"] and not record["infrastructure_result"] for record in records),
               "runtime_verification_rule_counts": dict(Counter(record["runtime_verification_rule"] or "not_recorded"
                   for record in records if record["first_skill_physically_executed"] and not record["infrastructure_result"])),
               "confusion": metrics["confusion"], "known_truth_audit": metrics["verifier_known_truth_audit"],
               "root_cause_counts": dict(Counter(record["root_cause_category"] for record in records)),
               "runtime_failure_reason_counts": dict(Counter(record["runtime_failure_reason"] for record in records if record["runtime_failure_reason"])),
               "unmeasured_reason_counts": dict(Counter(reason for record in records for reason in record["unmeasured_reasons"])),
               "private_mode_mismatches": sum(record["private_mode_mismatch"] for record in records),
               "registered_unique_raw_state_sha256": metrics["registered_unique_raw_initial_state_sha256"],
               "recorded_unique_raw_state_sha256": metrics["unique_raw_initial_state_sha256"],
               "nominal_resets": metrics["nominal_registered_resets"],
               "attempts": infra}
        table.append(row)
    source = {"snapshot": str(Path(source_snapshot).resolve()) if source_snapshot else None, "commit": source_commit,
              "summary_script_sha256": sha(__file__), "shared_summary_sha256": sha(sys.modules[summarize.__module__].__file__)}
    if source_snapshot:
        source["probe_sha256"] = sha(Path(source_snapshot) / "scripts/probe_v5_skill501_original.py")
    tails = [item for item in inputs if item.get("deferred_tail_bytes")]
    report.update(version="skill543-selection-summary/1", source=source, job_ids=list(job_ids),
                  original_explicit_inputs=inputs, deferred_inflight_tails=tails,
                  complete=report["complete"] and not tails, by_type_method=table,
                  placement_scopes=placement_scopes(diagnostics),
                  runtime_truth_scope="runtime receipts and private measured predicates are separate; already-satisfied endpoint preservation is not newly achieved skill success; infrastructure failure is not physical failure",
                  diagnostic_scope="six fixture types and on/in use the same recorded-evidence classification; inspect missing public binding, handle before/wrist, waypoint residuals, contact budget, requested-mode private joints and verifier disagreement in that order; no hidden replay or label-dependent control")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "case_diagnostics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in diagnostics))
    columns = ("type_method", "planned", "completed_case_records", "pending_case_records", "infrastructure_fault_cases",
               "unresolved_infrastructure_cases", "physical_first_attempts", "contact_vla_executed", "contact_vla_not_executed",
               "contact_vla_execution_unknown", "private_known", "private_successes",
               "runtime_verified_true", "runtime_verified_false", "runtime_verified_unmeasured", "private_success_wilson_95CI")
    (output / "by_type_method.tsv").write_text("\t".join(columns) + "\n" + "".join(
        "\t".join(json.dumps(row[column], separators=(",", ":")) for column in columns) + "\n" for row in table))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", default=[])
    parser.add_argument("--infrastructure-ledger", type=Path, action="append", default=[])
    parser.add_argument("--source-snapshot", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--job-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run_summary(args.manifest, args.ledger, args.infrastructure_ledger, args.output_dir,
                         source_snapshot=args.source_snapshot, source_commit=args.source_commit, job_ids=args.job_id)
    print(json.dumps({"complete": report["complete"], "recorded": report["overall"]["recorded"],
                      "qualification_authorized": False, "report": str(args.output_dir / "report.json"),
                      "sha256": sha(args.output_dir / "report.json")}))


if __name__ == "__main__":
    main()
