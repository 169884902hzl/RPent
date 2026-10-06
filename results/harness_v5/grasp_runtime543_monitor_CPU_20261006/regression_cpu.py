# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Pure synthetic ledger checks; no simulation or model execution."""

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts/summarize_v5_grasp543_20261006.py"
spec = importlib.util.spec_from_file_location("summary543", SCRIPT)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def fixture(root, cohort="independent_confirmation_synthetic", count=1, repeated=False):
    cases = [{"name": f"synthetic_{index}", "condition": "test", "group": "frypan",
              "state_sha256": hashlib.sha256(str(0 if repeated else index).encode()).hexdigest(),
              "episode": {"suite": "libero_90", "task": 18, "seed": index},
              "private_original_goal_predicates": [["on", "target", "stove"]]}
             for index in range(count)]
    plan = {"cohort": cohort, "cases": cases, "conditions": {"test": {}}}
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(plan))
    return manifest, summary.sha(manifest), cases


def attempt(case, output, index=0, physical=True, truth=True, verdict=True, infra=False):
    receipt = {"executed": physical, "grasp_verified": verdict, "stop": "synthetic"}
    return {"case": copy.deepcopy(case), "output_dir": str(output / case["name"]),
            "attempt_index": index, "first_receipt": receipt,
            "physical_execution_observed": physical, "true_sustained_grasp": truth,
            "visual_verified": verdict is True,
            "infrastructure_error": "TimeoutError(synthetic)" if infra else None,
            "case_had_infrastructure_failure": infra, "result": {"status": "synthetic"}}


def ledger(root, filename, rows):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


checks = []
with tempfile.TemporaryDirectory(prefix="grasp543_synthetic_") as temp:
    base = Path(temp)

    root = base / "postphysics"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    first = attempt(cases[0], root / "run", truth=None, infra=True)
    first["error_stage"] = "private_metrology"
    first["first_receipt"] = {}
    first["public_receipt_before_private_metrology"] = {"executed": True, "grasp_verified": True}
    first["visual_verified"] = False
    better = attempt(cases[0], root / "run", index=1)
    episodes = ledger(root / "run", "episodes.jsonl", [better])
    infrastructure = ledger(root / "run", "infrastructure_attempts.jsonl", [first])
    report, selected, roles = summary.summarize([manifest], [digest],
                                              [("episodes", episodes), ("infrastructure", infrastructure)])
    assert selected[0]["sustained_posttrial_grasp"] is None
    assert selected[0]["public_grasp_verdict"] is True
    assert roles[1]["role"] == "development_physical_repeat"
    assert report["retry_policy_violations"]
    checks.append("postphysics_unknown_retained_not_replaced_by_later_success")

    root = base / "recovered"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    failed = attempt(cases[0], root / "run", physical=False, truth=None, infra=True)
    retry = attempt(cases[0], root / "run", index=1)
    retry["case_had_infrastructure_failure"] = True
    infrastructure = ledger(root / "run", "infrastructure_attempts.jsonl", [failed])
    episodes = ledger(root / "run", "episodes.jsonl", [retry])
    events = ledger(root, "infrastructure_cases.jsonl", [
        {"case": cases[0]["name"], "manifest_sha256": digest, "planned_cases": 1,
         "infrastructure_failure": True},
        {"case": cases[0]["name"], "manifest_sha256": digest, "planned_cases": 1,
         "infrastructure_failure": False}])
    report, selected, roles = summary.summarize([manifest], [digest],
        [("episodes", episodes), ("infrastructure", infrastructure), ("infrastructure", events)])
    infra = report["infrastructure_by_manifest"][digest]
    assert len(selected) == 1 and selected[0]["attempt_index"] == 1
    assert infra["unique_affected_cases"] == 1 and infra["recovered_cases"] == [cases[0]["name"]]
    assert infra["retry_invocations"] == 1 and not report["retry_policy_violations"]
    checks.append("prephysics_once_retry_retains_infrastructure_fault_after_recovery")

    root = base / "subtask"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    row = attempt(cases[0], root / "run", truth=False)
    row["private_original_task_status_after"] = {
        "goals": [["on", "target", "stove"]], "satisfied": [True], "done": True}
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    assert selected[0]["official_on_subtask_success"] is True
    assert selected[0]["official_original_task_done"] is True
    assert selected[0]["sustained_posttrial_grasp"] is False
    assert selected[0]["sustained_during_complete_subtask"] is None
    checks.append("official_On_success_does_not_replace_sustained_grasp_truth")

    root = base / "unmeasured"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    row = attempt(cases[0], root / "run", verdict=None)
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert sum(metrics["confusion"].values()) == 0 and metrics["confusion"]["fn"] == 0
    assert metrics["known_truth_public_unmeasured"] == 1
    assert metrics["verifier_agreement"]["best_case_rate"] == 1
    checks.append("null_public_verdict_stays_unmeasured_not_FN")

    root = base / "selection"
    root.mkdir()
    manifest, digest, cases = fixture(root, "original_method_selection_correlated_resets", 100, True)
    episodes = ledger(root / "run", "episodes.jsonl", [attempt(case, root / "run") for case in cases])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert metrics["planned_correlated_repeat_requests"] == 99
    assert metrics["analysis_roles"] == ["selection"]
    assert not metrics["distinct_registered_confirmation_states"]
    assert metrics["single_class_threshold_evidence"] is None
    checks.append("correlated_selection_resets_are_not_independent_confirmation")

    root = base / "unknown_coverage"
    root.mkdir()
    manifest, digest, cases = fixture(root, count=100)
    rows = [attempt(case, root / "run") for case in cases]
    rows[-1]["true_sustained_grasp"] = None
    rows[0]["first_receipt"]["grasp_verified"] = False
    episodes = ledger(root / "run", "episodes.jsonl", rows)
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert metrics["truth_coverage"]["unknown_after_physics"] == 1
    assert metrics["physical_success"]["worst_case_rate"] == .99
    assert metrics["verifier_agreement"]["worst_case_rate"] == .98
    assert metrics["single_class_threshold_evidence"] == "supported_by_worst_case_bounds"
    assert report["full_six_class_qualification"] == "not_evaluated"
    checks.append("unknown_outcome_does_not_add_100_percent_truth_coverage_gate")

    try:
        summary.summarize([manifest], ["0" * 64], [])
    except ValueError as error:
        assert "SHA mismatch" in str(error)
    else:
        raise AssertionError("changed manifest accepted")
    checks.append("manifest_identity_is_pinned")

    root = base / "startup_TypeError"
    root.mkdir()
    manifest, digest, cases = fixture(root)
    row = attempt(cases[0], root / "run", physical=False, truth=None, verdict=None)
    row["first_receipt"] = {}
    row["raised_error"] = "TypeError('expected str, bytes or os.PathLike object, not dict')"
    row["result"] = {"status": "error", "termination_category": "startup_error"}
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes)])
    infra = report["infrastructure_by_manifest"][digest]
    metrics = next(iter(report["by_manifest_condition_group"].values()))
    assert not selected and sum(metrics["confusion"].values()) == 0
    assert infra["unique_affected_cases"] == 0
    assert infra["prephysics_unclassified_runtime_error_invocations"] == 1
    assert infra["unclassified_non_rpc_runtime_error_cases"] == [cases[0]["name"]]
    checks.append("4123_zero_physics_startup_TypeError_is_reported_without_physical_failure_label")

    root = base / "explicit_resume_source_strata"
    root.mkdir()
    manifest, digest, cases = fixture(root, cohort="method_selection_correlated_resets", count=4)
    resume = root / "resume.json"
    resume_plan = {"cohort": "method_selection_correlated_resets", "conditions": {"test": {"changed": True}},
                   "parent_manifest": {"sha256": digest}, "cases": [cases[1], cases[3]]}
    resume.write_text(json.dumps(resume_plan))
    resume_digest = summary.sha(resume)
    zero_bug = attempt(cases[1], root / "old", physical=False, truth=None, verdict=None)
    zero_bug["raised_error"] = "AttributeError('NoneType object has no attribute name')"
    ordinary = attempt(cases[2], root / "old", physical=False, truth=None, verdict=None)
    ordinary["first_receipt"]["failure_reason"] = "visible_handle_not_measured"
    old = ledger(root / "old", "episodes.jsonl", [attempt(cases[0], root / "old", truth=False), zero_bug, ordinary])
    new = ledger(root / "new", "episodes.jsonl", [attempt(case, root / "new") for case in resume_plan["cases"]])
    events = ledger(root / "new", "infrastructure_cases.jsonl", [
        {"case": cases[3]["name"], "manifest_sha256": resume_digest, "planned_cases": 2,
         "infrastructure_failure": True}])
    report, selected, roles = summary.summarize([manifest], [digest], [
        ("episodes", old, "SOURCE544", digest), ("episodes", new, "SOURCE546", resume_digest),
        ("infrastructure", events, "SOURCE546", resume_digest)], [resume], [resume_digest])
    assert report["planned"] == 4 and len(selected) == 3 and len(roles) == 5
    assert selected[0]["sustained_posttrial_grasp"] is False
    assert next(row for row in selected if row["case"] == cases[1]["name"])["resumes_zero_physics_development_fault"]
    assert not report["retry_policy_violations"]
    assert report["infrastructure_by_manifest"][digest]["unique_affected_cases"] == 1
    strata = list(report["by_source_manifest_condition_group"].values())
    assert {row["source_stratum"]: row["first_physical_attempts"] for row in strata} == {"SOURCE544": 1, "SOURCE546": 2}
    assert {row["source_stratum"]: row["planned"] for row in strata} == {"SOURCE544": 4, "SOURCE546": 2}
    checks.append("resume_subset_maps_to_canonical_denominator_preserves_old_physics_and_source_strata")

    changed = copy.deepcopy(resume_plan)
    changed["cases"][0]["state_sha256"] = "f" * 64
    bad_resume = root / "changed_resume.json"
    bad_resume.write_text(json.dumps(changed))
    try:
        summary.summarize([manifest], [digest], [], [bad_resume], [summary.sha(bad_resume)])
    except ValueError as error:
        assert "changed or unregistered execution manifest case" in str(error)
    else:
        raise AssertionError("resume changed canonical case identity")
    checks.append("execution_subset_cannot_change_canonical_case_identity")

    ordinary_restart = ledger(root / "ordinary_new", "episodes.jsonl", [attempt(cases[2], root / "ordinary_new")])
    report, selected, roles = summary.summarize([manifest], [digest], [
        ("episodes", old, "SOURCE544", digest), ("episodes", ordinary_restart, "SOURCE546", digest)])
    assert any(v["case"] == cases[2]["name"] and v["reason"] == "reexecution_after_non_infrastructure_outcome"
               for v in report["retry_policy_violations"])
    checks.append("source_change_does_not_authorize_restart_of_ordinary_nonphysical_failure")

    fixed = ledger(root / "fixed", "episodes.jsonl", [attempt(cases[1], root / "fixed")])
    report, selected, roles = summary.summarize([manifest], [digest], [
        ("episodes", old, "SOURCE544", digest), ("episodes", fixed, "SOURCE545", digest)])
    assert next(row for row in selected if row["case"] == cases[1]["name"])["resumes_zero_physics_development_fault"]
    assert not report["retry_policy_violations"]
    checks.append("zero_physics_development_fix_can_keep_the_same_registered_manifest")

    root = base / "complete_subtask_primary_predicate"
    root.mkdir()
    manifest, digest, cases = fixture(root, cohort="method_selection_correlated_resets")
    cases[0]["condition"] = "moka_original_complete_subtask"
    manifest.write_text(json.dumps({"cohort": "method_selection_correlated_resets", "cases": cases,
                                   "conditions": {"moka_original_complete_subtask": {}}}))
    digest = summary.sha(manifest)
    row = attempt(cases[0], root / "run", truth=False, verdict=False)
    row["private_original_task_status_before"] = {
        "goals": [["on", "target", "stove"]], "satisfied": [False], "done": False}
    row["private_original_task_status_after"] = {
        "goals": [["on", "target", "stove"]], "satisfied": [True], "done": True}
    row["private_grasp_phase"] = {"true_sustained_grasp_during_skill": True,
                                  "true_sustained_grasp_at_end": False}
    episodes = ledger(root / "run", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes, "SOURCE546", digest)])
    metric = next(iter(report["by_manifest_condition_group"].values()))
    assert metric["primary_outcome_kind"] == "selected_original_subtask_On_predicate"
    assert metric["primary_success"]["successes"] == 1
    assert metric["physical_success"]["successes"] == 0
    assert selected[0]["diagnostic_failure_type"] == "selected_original_subtask_satisfied_posttrial_not_held"
    assert selected[0]["placement_predicate_became_true_after_execution"] is True
    assert selected[0]["target_placement_satisfied_with_end_not_held"] is True
    assert selected[0]["public_object_release_observed"] is None
    assert selected[0]["sustained_during_complete_subtask"] is True
    assert selected[0]["sustained_at_end_of_complete_subtask"] is False
    assert selected[0]["end_not_held_is_full_subtask_failure"] is False
    checks.append("complete_subtask_placement_is_primary_success_while_hold_and_release_evidence_stay_separate")

    row["private_original_task_status_after"]["satisfied"] = [False]
    episodes = ledger(root / "done_wrong_selected_predicate", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes, "SOURCE546", digest)])
    metric = next(iter(report["by_manifest_condition_group"].values()))
    assert selected[0]["official_original_task_done"] is True
    assert metric["primary_success"]["known"] == 1 and metric["primary_success"]["successes"] == 0
    row["private_original_task_status_after"] = {
        "goals": [["on", "target", "different_destination"]], "satisfied": [True], "done": True}
    episodes = ledger(root / "different_destination", "episodes.jsonl", [row])
    report, selected, roles = summary.summarize([manifest], [digest], [("episodes", episodes, "SOURCE546", digest)])
    metric = next(iter(report["by_manifest_condition_group"].values()))
    assert selected[0]["official_on_subtask_success"] is None and metric["primary_success"]["known"] == 0
    checks.append("complete_subtask_done_or_wrong_On_destination_cannot_replace_selected_registered_predicate")

result = {"synthetic_data_only": True, "checks": checks, "passed": len(checks),
          "summary_script_sha256": summary.sha(SCRIPT), "python": sys.executable,
          "new_physical_trials": 0, "new_training_rows": 0}
(Path(__file__).parent / "regression_results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
