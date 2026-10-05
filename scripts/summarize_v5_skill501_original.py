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

from scripts.probe_v5_skill501_original import executed_actions, sha, validate_manifest
from scripts.summarize_v5_grasp449_20261005 import wilson


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


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
    counts, failures, runtime_matrix = Counter(), Counter(), Counter()
    for row in rows:
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
            "public_witness_scope": "read-only public visual witness; recorded version identifies legacy or independent-frame checks; distinct from final runtime place receipt and not a sustained-grasp verifier",
            "truth_scope": "0.5s continuous supported-clearance window sampled at every simulator control step; final release reported separately"}


def metrics(rows, planned):
    counts, failures, matrix, setup_counts = Counter(), Counter(), Counter(), Counter()
    wall_times, scene_keys = [], set()
    for row in rows:
        case = row["case"]
        scene_keys.add(tuple(case["episode"][key] for key in ("suite", "task", "seed")))
        wall_times.append(row["wall_s"])
        status = row["status"]
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
            "newly_satisfied_rate": ratio(counts["newly_satisfied"], counts["known_initially_unsatisfied"]),
            "failure_counts": dict(failures), "unique_original_initial_states": len(scene_keys),
            "median_wall_s": statistics.median(wall_times) if wall_times else None,
            "numeric_first_place_targets_met": bool(is_place and first_place >= 100
                and ratio(counts["true_first_place_successes"], first_place) >= .90
                and ratio(matrix["tp"], matrix["tp"] + matrix["fp"]) is not None
                and ratio(matrix["tp"], matrix["tp"] + matrix["fp"]) >= .95)}


def summarize(manifest_paths, ledger_paths):
    planned, manifests, conditions = {}, [], {}
    for path in map(Path, manifest_paths):
        plan = json.loads(path.read_text())
        validate_manifest(plan)
        manifests.append({"path": str(path), "sha256": sha(path)})
        for name, condition in plan["conditions"].items():
            if name in conditions and conditions[name] != condition:
                raise ValueError("same condition name has different registered settings")
            conditions[name] = condition
        for case in plan["cases"]:
            if case["name"] in planned:
                raise ValueError("duplicate manifest case")
            planned[case["name"]] = case
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
    planned_groups = Counter((case["type"], case["condition"]) for case in planned.values())
    recorded_groups = defaultdict(list)
    for row in rows:
        recorded_groups[row["case"]["type"], row["case"]["condition"]].append(row)
    groups = {f"{kind}/{condition}": metrics(recorded_groups[kind, condition], size)
              for (kind, condition), size in sorted(planned_groups.items())}
    grasp_groups = {f"{kind}/{condition}": grasp_phase_metrics(recorded_groups[kind, condition], size)
                    for (kind, condition), size in sorted(planned_groups.items())
                    if all(case["kind"] == "grasp_then_subtask" for case in planned.values()
                           if (case["type"], case["condition"]) == (kind, condition))}
    return {"scope": "original-only paired skill exploration; no confirmation, behavior freeze, or training admission",
            "manifests": manifests, "ledgers": ledgers, "conditions": conditions,
            "script_sha256": sha(__file__), "python": sys.executable,
            "truth_source": "private official subgoal predicates, fixture qpos or post-receipt0.5s sustained grasp; labels never replace public receipts",
            "setup_source": "real measured skills or registered public robot motion; no simulation attach; private grasp quality reported separately",
            "public_unmeasured_policy": "null stays unmeasured and is excluded from measured verifier confusion, with coverage reported",
            "first_place_denominators": "true setup executed attempts and all preregistered attempts reported separately",
            "ci_scope": "nominal Wilson binomial intervals; repeated initial states disclosed, no independence or qualification claim",
            "overall": metrics(rows, len(planned)), "by_type_condition": groups,
            "fixture_mode_audit": [fixture_mode_audit(row) for row in rows if row["case"]["kind"] == "articulate"],
            "grasp_phase_by_type_condition": grasp_groups,
            "grasp_phase_overall": grasp_phase_metrics(
                [row for row in rows if row["case"]["kind"] == "grasp_then_subtask"],
                sum(case["kind"] == "grasp_then_subtask" for case in planned.values())),
            "complete": seen == planned.keys() and not missing_ledgers and not missing_choices,
            "missing_cases": sorted(planned.keys() - seen), "missing_ledgers": missing_ledgers,
            "missing_choices": missing_choices, "qualification_authorized": False,
            "new_training_rows": 0, "new_physical_trials": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.manifest, args.ledger)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"complete": report["complete"], "recorded": report["overall"]["recorded"],
                      "qualification_authorized": False, "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
