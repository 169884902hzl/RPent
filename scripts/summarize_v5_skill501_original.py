"""Summarize explicitly registered original grasp, place and fixture probes.

These repeated-reset explorations do not authorize confirmation, harness
freeze, or training. Unknown visual evidence stays unmeasured even when the
private predicate is available.
"""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys

from scripts.probe_v5_skill501_original import executed_actions, row_infrastructure_failure, sha, validate_manifest
from scripts.summarize_v5_grasp449_20261005 import wilson


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def infrastructure_result(row):
    return row.get("status") == "infrastructure_error" or row_infrastructure_failure(row)


def verifier_audit(matrix, known, observed, planned, unmeasured_positive=0, unmeasured_negative=0):
    """Abstentions remain in known-truth agreement without becoming FP/FN."""
    measured = sum(matrix[key] for key in ("tp", "tn", "fp", "fn"))
    agreement = matrix["tp"] + matrix["tn"]
    positives, negatives = matrix["tp"] + matrix["fn"], matrix["fp"] + matrix["tn"]
    denominators = {
        "agreement_over_known_private_truth": (agreement, known),
        "agreement_over_planned_lower_bound": (agreement, planned),
        "public_measurement_coverage": (measured, known),
        "private_truth_coverage_over_observed": (known, observed),
        "private_truth_coverage_over_planned": (known, planned),
        "precision": (matrix["tp"], matrix["tp"] + matrix["fp"]),
        "recall": (matrix["tp"], positives),
        "recall_over_known_private_positive_lower_bound": (matrix["tp"], positives + unmeasured_positive),
        "false_positive_rate": (matrix["fp"], negatives),
        "false_negative_rate": (matrix["fn"], positives),
    }
    return {
        "known_private_truth": known, "unknown_private_truth": observed - known,
        "public_measured_on_known_truth": measured,
        "public_unmeasured_on_known_truth": unmeasured_positive + unmeasured_negative,
        "unmeasured_private_positive": unmeasured_positive,
        "unmeasured_private_negative": unmeasured_negative,
        "rates": {key: {"count": numerator, "denominator": denominator,
                         "rate": ratio(numerator, denominator), "wilson_95CI": wilson(numerator, denominator)}
                  for key, (numerator, denominator) in denominators.items()},
        "scope": "known-truth agreement includes unmeasured public verdicts in its denominator; they stay unmeasured, not FP/FN; precision/recall/FP/FN use explicitly disclosed measured denominators; planned lower bound also retains missing, unknown and infrastructure-unavailable cases; no qualification claim",
    }


def fixture_mode_audit(row):
    """Expose whether truth evaluates each setup's own requested predicate."""
    def stage_audit(spec, stage):
        mode = spec["mode"]
        requested_predicate = {"turn_on": "turnon", "turn_off": "turnoff"}.get(mode, mode)
        before, after = stage.get("private_before", {}), stage.get("private_after", {})
        before_predicate = before.get("predicate", [])
        after_predicate = after.get("predicate", [])
        before_mode = before_predicate[0] if before_predicate else None
        after_mode = after_predicate[0] if after_predicate else None
        return {"action": stage["selected"], "spec_mode": mode,
                "receipt_mode": stage.get("receipt", {}).get("mode"),
                "expected_private_predicate_mode": requested_predicate,
                "private_before_queried_mode": before_mode, "private_after_queried_mode": after_mode,
                "private_before_predicate": before_predicate, "private_after_predicate": after_predicate,
                "private_before": before.get("satisfied"), "private_after": after.get("satisfied"),
                "queried_requested_mode": (before_mode == after_mode == requested_predicate
                                           if before_mode is not None and after_mode is not None else None)}
    case = row["case"]
    if case["kind"] != "articulate":
        return None
    stages = row.get("setup", [])
    if len(stages) > len(case.get("setup", [])):
        raise ValueError("more recorded setup actions than registered specifications")
    setup = [stage_audit(spec, stage) for spec, stage in zip(case.get("setup", []), stages)]
    first = stage_audit(case, row["first_attempt"]) if row.get("first_attempt") else None
    return {"case": case["name"], "status": row["status"], "setup": setup, "first_attempt": first,
            "scope": "private modes are queried independently for setup and first; setup is not judged by the reverse first target"}


def setup_truth(row):
    """Private setup quality is a reported stratum, not a runtime gate."""
    if row["case"]["kind"] != "place":
        return None
    grasps = [stage for stage in row.get("setup", [])
              if stage.get("receipt", {}).get("tool") == "grasp"]
    if not grasps:
        return None
    values = [stage.get("private_true_sustained_grasp") for stage in grasps]
    if any(value is False for value in values):
        return False
    return True if all(value is True for value in values) else None


def grasp_phase_metrics(rows, planned):
    """Final placement/release must not redefine the earlier grasp phase."""
    counts, failures, runtime_matrix, end_truth = Counter(), Counter(), Counter(), Counter()
    for row in rows:
        if infrastructure_result(row):
            counts["infrastructure_results_excluded"] += 1
            continue
        stage = row.get("first_attempt")
        if stage is None:
            failures[row["status"]] += 1
            continue
        evidence = stage.get("contact_evidence", {})
        counts["contact_executed"] += int(evidence.get("executed_vla_actions", 0) > 0)
        phase = row.get("private_grasp_phase", {})
        during = phase.get("true_sustained_grasp_during_skill")
        ending = phase.get("true_sustained_grasp_at_end")
        if isinstance(during, bool):
            counts["known_grasp_phase_truth"] += 1
            counts["true_sustained_grasp_during_skill"] += int(during)
        else:
            failures["private_grasp_phase_truth_unavailable"] += 1
        if ending is True:
            counts["still_sustained_at_end"] += 1
        public_grasp = stage.get("receipt", {}).get("grasp_verified")
        end_truth["observed"] += 1
        if isinstance(ending, bool):
            end_truth["known"] += 1
            if public_grasp is None:
                end_truth["unmeasured_positive" if ending else "unmeasured_negative"] += 1
        if isinstance(public_grasp, bool) and isinstance(ending, bool):
            runtime_matrix["tp" if public_grasp and ending else "fp" if public_grasp else
                           "fn" if ending else "tn"] += 1
        elif public_grasp is None:
            runtime_matrix["public_grasp_not_measured"] += 1
        else:
            runtime_matrix["private_end_truth_unknown"] += 1
        completed = stage.get("private_after", {}).get("satisfied")
        if isinstance(completed, bool):
            counts["known_subtask_truth"] += 1
            counts["subtask_completed"] += int(completed)
            if completed and during is True and ending is False:
                counts["sustained_grasp_then_completed_release"] += 1
        if evidence.get("public_grasp_observations"):
            counts["public_visual_grasp_witness"] += 1
            if during is True:
                counts["public_witness_with_sustained_truth"] += 1
            elif during is False:
                counts["public_witness_without_sustained_truth"] += 1
        if row.get("raised_error"):
            failures["probe_error"] += 1
    measured = sum(runtime_matrix[key] for key in ("tp", "tn", "fp", "fn"))
    return {"planned": planned, "recorded": len(rows), "counts": dict(counts),
            "grasp_during_skill_success_rate": ratio(counts["true_sustained_grasp_during_skill"],
                                                     counts["known_grasp_phase_truth"]),
            "grasp_during_skill_success_over_planned": ratio(counts["true_sustained_grasp_during_skill"], planned),
            "grasp_during_skill_wilson_95CI": wilson(counts["true_sustained_grasp_during_skill"],
                                                    counts["known_grasp_phase_truth"]),
            "subtask_completion_rate": ratio(counts["subtask_completed"], counts["known_subtask_truth"]),
            "subtask_completion_over_planned": ratio(counts["subtask_completed"], planned),
            "failure_counts": dict(failures),
            "runtime_grasp_verifier_against_end_hold": {
                "confusion": dict(runtime_matrix), "measured": measured,
                "false_positive_count": runtime_matrix["fp"], "false_negative_count": runtime_matrix["fn"],
                "agreement": ratio(runtime_matrix["tp"] + runtime_matrix["tn"], measured),
                "false_positive_rate": ratio(runtime_matrix["fp"], runtime_matrix["fp"] + runtime_matrix["tn"]),
                "false_negative_rate": ratio(runtime_matrix["fn"], runtime_matrix["fn"] + runtime_matrix["tp"]),
                "scope": "actual runtime grasp_verified versus sustained hold at skill end; full-transfer macros without a grasp verdict are unmeasured, not failed grasps"},
            "runtime_grasp_verifier_known_truth_audit": verifier_audit(
                runtime_matrix, end_truth["known"], end_truth["observed"], planned,
                end_truth["unmeasured_positive"], end_truth["unmeasured_negative"]),
            "public_witness_scope": "read-only public visual witness; recorded version identifies legacy or independent-frame checks; distinct from final runtime place receipt and not a sustained-grasp verifier",
            "truth_scope": "0.5s continuous supported-clearance window sampled at every simulator control step; final release reported separately"}


def metrics(rows, planned, registered_cases=None):
    counts, failures, matrix, setup_counts = Counter(), Counter(), Counter(), Counter()
    wall_times, scene_keys = [], set()
    for row in rows:
        case = row["case"]
        scene_keys.add(tuple(case["episode"][key] for key in ("suite", "task", "seed")))
        wall_times.append(row["wall_s"])
        status = row["status"]
        if infrastructure_result(row):
            counts["infrastructure_results_excluded"] += 1
            continue
        stage = row.get("first_attempt")
        private_setup = setup_truth(row)
        if case["kind"] == "place":
            setup_counts["true_sustained_grasp" if private_setup is True else
                         "false_sustained_grasp" if private_setup is False else "unknown_sustained_grasp"] += 1
        if stage is None:
            counts["first_attempt_not_executed"] += 1
            failures[status] += 1
            if status.startswith("setup_"):
                counts["setup_failed"] += 1
            continue
        counts["first_attempt_recorded"] += 1
        physically_executed = executed_actions(stage["motion_evidence"]) > 0
        if physically_executed != stage["physically_executed"]:
            raise ValueError("physical execution flag differs from recorded motion evidence")
        if not physically_executed:
            counts["first_attempt_not_executed"] += 1
            failures["no_physical_execution"] += 1
            continue
        counts["first_attempt_executed"] += 1
        if case["kind"] == "place" and private_setup is True:
            counts["first_place_with_true_setup"] += 1
        before = stage.get("private_before", {}).get("satisfied")
        truth = (stage.get("private_true_sustained_grasp") if case["kind"] == "grasp"
                 else stage.get("private_after", {}).get("satisfied"))
        receipt = stage["receipt"]
        verified = receipt.get("grasp_verified" if case["kind"] == "grasp" else
                               "place_verified" if case["kind"] in {"place", "grasp_then_subtask"} else "articulate_verified")
        if not isinstance(truth, bool):
            counts["unknown_private_truth"] += 1
            failures["private_truth_unavailable"] += 1
            continue
        counts["known_private_truth"] += 1
        if truth:
            counts["true_successes"] += 1
            if case["kind"] == "place" and private_setup is True:
                counts["true_first_place_successes"] += 1
        if before is True:
            counts["predicate_already_satisfied_before_attempt"] += 1
        elif before is False:
            counts["known_initially_unsatisfied"] += 1
            counts["newly_satisfied"] += int(truth)
        if verified is None:
            counts["public_unmeasured"] += 1
            matrix["unmeasured_private_positive" if truth else "unmeasured_private_negative"] += 1
        elif isinstance(verified, bool):
            counts["public_measured"] += 1
            matrix["tp" if truth and verified else "fn" if truth else "fp" if verified else "tn"] += 1
        else:
            raise ValueError("public verification must be true, false, or null")
        if receipt.get("verification") == "execution_error" or receipt.get("error"):
            failures["execution_error"] += 1
        elif not truth:
            failures[receipt.get("failure_reason", "sustained_grasp_false" if case["kind"] == "grasp"
                                 else "official_predicate_false")] += 1
        if row.get("raised_error"):
            failures["probe_error"] += 1
    known = counts["known_private_truth"]
    measured = counts["public_measured"]
    positives = matrix["tp"] + matrix["fn"]
    negatives = matrix["fp"] + matrix["tn"]
    is_place = any(row["case"]["kind"] == "place" for row in rows)
    first_place = counts["first_place_with_true_setup"]
    audit = verifier_audit(matrix, known, counts["first_attempt_executed"], planned,
                           matrix["unmeasured_private_positive"], matrix["unmeasured_private_negative"])
    registered_cases = list(registered_cases) if registered_cases is not None else [row["case"] for row in rows]
    return {"planned": planned, "recorded": len(rows), "missing": planned - len(rows),
            "counts": dict(counts), "setup_private_truth": dict(setup_counts),
            "first_attempt_executed": counts["first_attempt_executed"],
            "known_truth": known, "true_successes": counts["true_successes"],
            "success_over_executed_known": ratio(counts["true_successes"], known),
            "success_over_planned": ratio(counts["true_successes"], planned),
            "wilson_95CI": wilson(counts["true_successes"], known),
            "first_place_success_over_true_setup": ratio(counts["true_first_place_successes"], first_place),
            "first_place_wilson_95CI": wilson(counts["true_first_place_successes"], first_place),
            "first_place_true_setup_coverage_over_planned": ratio(first_place, planned) if is_place else None,
            "confusion": dict(matrix), "public_unmeasured": counts["public_unmeasured"],
            "public_measurement_coverage": ratio(measured, known),
            "precision": ratio(matrix["tp"], matrix["tp"] + matrix["fp"]),
            "recall": ratio(matrix["tp"], positives),
            "agreement_over_measured": ratio(matrix["tp"] + matrix["tn"], measured),
            "false_positive_rate": ratio(matrix["fp"], negatives),
            "false_negative_rate": ratio(matrix["fn"], positives),
            "false_positive_count": matrix["fp"], "false_negative_count": matrix["fn"],
            "agreement_over_known_private_truth": audit["rates"]["agreement_over_known_private_truth"]["rate"],
            "agreement_over_known_private_truth_wilson_95CI": audit["rates"]["agreement_over_known_private_truth"]["wilson_95CI"],
            **{key + "_wilson_95CI": audit["rates"][key]["wilson_95CI"]
               for key in ("public_measurement_coverage", "precision", "recall", "false_positive_rate", "false_negative_rate")},
            "verifier_known_truth_audit": audit,
            "newly_satisfied_rate": ratio(counts["newly_satisfied"], counts["known_initially_unsatisfied"]),
            "failure_counts": dict(failures), "unique_original_initial_states": len(scene_keys),
            "unique_raw_initial_state_sha256": len({row["case"]["state_sha256"] for row in rows}),
            "registered_unique_raw_initial_state_sha256": len({case["state_sha256"] for case in registered_cases}),
            "nominal_registered_resets": planned, "nominal_recorded_resets": len(rows),
            "reset_scope": "one nominal reset per registered case; same raw state SHA across conditions/repetitions is not an independent initial state; infrastructure attempts/retries are reported separately",
            "median_wall_s": statistics.median(wall_times) if wall_times else None,
            "numeric_first_place_targets_met": bool(is_place and first_place >= 100
                and ratio(counts["true_first_place_successes"], first_place) >= .90
                and ratio(matrix["tp"], matrix["tp"] + matrix["fp"]) is not None
                and ratio(matrix["tp"], matrix["tp"] + matrix["fp"]) >= .95),
            "numeric_first_place_targets_scope": "legacy numeric targets using true-setup execution and measured precision only; unknown/unmeasured coverage is disclosed separately; not confirmation or admission"}


def infrastructure_metrics(rows, planned, attempt_records, case_events):
    """Count invocations separately from case outcomes, without opening references."""
    attempts, explicit_keys = {}, set()
    for record in attempt_records:
        case = record["case"]
        name, index = case["name"], record["attempt_index"]
        if case != planned.get(name) or not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("changed or unregistered infrastructure attempt")
        if record.get("registered_state_sha256", case["state_sha256"]) != case["state_sha256"]:
            raise ValueError("infrastructure attempt changed raw initial state")
        key = (name, index)
        if key in attempts:
            raise ValueError("duplicated explicit infrastructure attempt")
        attempts[key] = record
        explicit_keys.add(key)
    legacy_rows = 0
    for row in rows:
        references = row.get("attempts")
        if references is None:
            references = [row]
            legacy_rows += "attempt_index" not in row
        for reference in references:
            case = row["case"]
            index = reference.get("attempt_index", 0)
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise ValueError("invalid embedded infrastructure attempt index")
            if reference.get("registered_state_sha256", case["state_sha256"]) != case["state_sha256"]:
                raise ValueError("embedded attempt changed raw initial state")
            key = (case["name"], index)
            record = {**reference, "case": case, "attempt_index": index}
            if key in attempts:
                prior = attempts[key]
                if (prior.get("status") != record.get("status")
                        or bool(prior.get("infrastructure_failure")) != bool(record.get("infrastructure_failure"))):
                    raise ValueError("explicit attempt differs from final case ledger")
                continue
            attempts[key] = record
    faulty = {row["case"]["name"] for row in rows if row.get("case_had_infrastructure_failure") or infrastructure_result(row)}
    for event in case_events:
        name = event["case"]
        if name not in planned:
            raise ValueError("unregistered infrastructure case event")
        if event.get("infrastructure_failure"):
            faulty.add(name)
    counts, statuses, categories = Counter(), Counter(), Counter()
    for (name, index), record in attempts.items():
        failed = infrastructure_result(record)
        counts["initial_attempts" if index == 0 else "retry_attempts"] += 1
        counts["infrastructure_failed_attempts" if failed else "non_infrastructure_attempts"] += 1
        statuses[record.get("status", "unknown")] += 1
        if failed:
            faulty.add(name)
            categories[record.get("failure_category", "category_not_recorded")] += 1
    unresolved = {row["case"]["name"] for row in rows if infrastructure_result(row)}
    resolved = {row["case"]["name"] for row in rows if not infrastructure_result(row)}
    return {"planned_cases": len(planned), "recorded_case_outcomes": len(rows),
            "attempts_recorded": len(attempts), "counts": dict(counts),
            "attempt_status_counts": dict(statuses), "infrastructure_failure_categories": dict(categories),
            "cases_with_recorded_infrastructure_fault": len(faulty),
            "infrastructure_fault_rate_over_planned": ratio(len(faulty), len(planned)),
            "infrastructure_fault_rate_wilson_95CI": wilson(len(faulty), len(planned)),
            "unresolved_infrastructure_cases": len(unresolved),
            "recovered_infrastructure_cases": len(faulty & resolved),
            "explicit_attempt_records": len(explicit_keys),
            "embedded_or_legacy_attempt_records": len(attempts) - len(explicit_keys),
            "legacy_final_rows_assumed_single_attempt": legacy_rows,
            "explicit_case_event_records": len(case_events),
            "scope": "explicit infrastructure ledgers plus already-loaded case attempt metadata only; no directory search or inferred attempt files; legacy final rows establish only one nominal invocation; infrastructure faults are unavailable physical outcomes, not physical failures"}


def summarize(manifest_paths, ledger_paths, infrastructure_ledger_paths=()):
    planned, manifests, conditions = {}, [], {}
    infrastructure_references, manifest_by_case = [], {}
    for path in map(Path, manifest_paths):
        plan = json.loads(path.read_text())
        validate_manifest(plan)
        manifests.append({"path": str(path), "sha256": sha(path)})
        for reference in plan.get("infrastructure_ledgers", []):
            reference = {"path": reference} if isinstance(reference, str) else dict(reference)
            reference_path = Path(reference["path"]).expanduser()
            if not reference_path.is_absolute():
                reference_path = path.parent / reference_path
            infrastructure_references.append({**reference, "path": str(reference_path)})
        for name, condition in plan["conditions"].items():
            if name in conditions and conditions[name] != condition:
                raise ValueError("same condition name has different registered settings")
            conditions[name] = condition
        for case in plan["cases"]:
            if case["name"] in planned:
                raise ValueError("duplicate manifest case")
            planned[case["name"]] = case
            manifest_by_case[case["name"]] = manifests[-1]["sha256"]
    rows, ledgers, seen, missing_ledgers, missing_choices = [], [], set(), [], []
    for path in map(Path, ledger_paths):
        if not path.is_file():
            missing_ledgers.append(str(path))
            continue
        ledgers.append({"path": str(path), "sha256": sha(path)})
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            name = row["case"]["name"]
            if row["case"] != planned.get(name) or name in seen:
                raise ValueError("changed, unregistered, or duplicated physical trial")
            trace = Path(row["output_dir"]) / "choices.jsonl"
            if not trace.is_file():
                missing_choices.append({"case": name, "path": str(trace)})
            elif sha(trace) != row.get("choices_sha256"):
                raise ValueError("physical trace SHA differs from ledger: " + name)
            seen.add(name)
            rows.append(row)
    infrastructure_references.extend({"path": str(path)} for path in infrastructure_ledger_paths)
    infrastructure_ledgers, missing_infrastructure_ledgers, attempt_records, case_events = [], [], [], []
    read_infrastructure_paths = set()
    for reference in infrastructure_references:
        path = Path(reference["path"]).expanduser().resolve()
        if path in read_infrastructure_paths:
            raise ValueError("duplicated explicit infrastructure ledger")
        read_infrastructure_paths.add(path)
        if not path.is_file():
            missing_infrastructure_ledgers.append(str(path))
            continue
        digest = sha(path)
        if reference.get("sha256") is not None and reference["sha256"] != digest:
            raise ValueError("registered infrastructure ledger SHA changed")
        infrastructure_ledgers.append({"path": str(path), "sha256": digest})
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if isinstance(record.get("case"), dict):
                attempt_records.append(record)
            elif isinstance(record.get("case"), str):
                name = record["case"]
                if record.get("manifest_sha256") != manifest_by_case.get(name):
                    raise ValueError("infrastructure case event has unregistered manifest identity")
                case_events.append(record)
            else:
                raise ValueError("infrastructure ledger needs a registered attempt or case event")
    planned_groups = Counter((case["type"], case["condition"]) for case in planned.values())
    recorded_groups = defaultdict(list)
    for row in rows:
        recorded_groups[row["case"]["type"], row["case"]["condition"]].append(row)
    groups = {f"{kind}/{condition}": metrics(recorded_groups[kind, condition], size,
                  [case for case in planned.values() if (case["type"], case["condition"]) == (kind, condition)])
              for (kind, condition), size in sorted(planned_groups.items())}
    infrastructure_groups = {}
    for kind, condition in sorted(planned_groups):
        subset = {name: case for name, case in planned.items() if (case["type"], case["condition"]) == (kind, condition)}
        infrastructure_groups[f"{kind}/{condition}"] = infrastructure_metrics(
            recorded_groups[kind, condition], subset,
            [record for record in attempt_records if record["case"]["name"] in subset],
            [record for record in case_events if record["case"] in subset])
    infrastructure = infrastructure_metrics(rows, planned, attempt_records, case_events)
    grasp_groups = {f"{kind}/{condition}": grasp_phase_metrics(recorded_groups[kind, condition], size)
                    for (kind, condition), size in sorted(planned_groups.items())
                    if all(case["kind"] == "grasp_then_subtask" for case in planned.values()
                           if (case["type"], case["condition"]) == (kind, condition))}
    return {"scope": "original-only paired skill exploration; no confirmation, behavior freeze, or training admission",
            "manifests": manifests, "ledgers": ledgers, "conditions": conditions,
            "script_sha256": sha(__file__), "python": sys.executable,
            "truth_source": "private official subgoal predicates, fixture qpos or post-receipt0.5s sustained grasp; labels never replace public receipts",
            "setup_source": "real measured skills or registered public robot motion; no simulation attach; private grasp quality reported separately",
            "public_unmeasured_policy": "null stays unmeasured; legacy measured-only confusion remains, while known-private-truth agreement retains null verdicts in its denominator; unknown truth, missing cases and infrastructure-unavailable outcomes remain explicit in coverage and planned lower bounds",
            "first_place_denominators": "true setup executed attempts and all preregistered attempts reported separately",
            "ci_scope": "nominal Wilson binomial intervals; repeated initial states disclosed, no independence or qualification claim",
            "overall": metrics(rows, len(planned), planned.values()), "by_type_condition": groups,
            "infrastructure": infrastructure, "infrastructure_by_type_condition": infrastructure_groups,
            "infrastructure_ledgers": infrastructure_ledgers,
            "missing_infrastructure_ledgers": missing_infrastructure_ledgers,
            "fixture_mode_audit": [fixture_mode_audit(row) for row in rows if row["case"]["kind"] == "articulate"],
            "grasp_phase_by_type_condition": grasp_groups,
            "grasp_phase_overall": grasp_phase_metrics(
                [row for row in rows if row["case"]["kind"] == "grasp_then_subtask"],
                sum(case["kind"] == "grasp_then_subtask" for case in planned.values())),
            "complete": seen == planned.keys() and not missing_ledgers and not missing_choices and not missing_infrastructure_ledgers,
            "missing_cases": sorted(planned.keys() - seen), "missing_ledgers": missing_ledgers,
            "missing_choices": missing_choices, "qualification_authorized": False,
            "new_training_rows": 0, "new_physical_trials": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--infrastructure-ledger", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.manifest, args.ledger, args.infrastructure_ledger)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "recorded": report["overall"]["recorded"],
                      "qualification_authorized": False, "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
