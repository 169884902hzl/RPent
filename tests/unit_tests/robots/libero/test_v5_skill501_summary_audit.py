"""Skill summaries disclose abstentions, raw reset identity and service retries."""

import json
from pathlib import Path

import pytest

from scripts import summarize_v5_skill501_original as summary


def case(name="case0", digest="a" * 64, seed=10):
    return {"name": name, "kind": "place", "type": "place_on", "mode": "on",
            "condition": "current160", "state_sha256": digest,
            "episode": {"suite": "libero_goal", "task": 0, "seed": seed},
            "object_symbol": "bowl", "target_symbol": "plate", "setup": []}


def row(chosen=None, truth=True, verdict=True):
    return {"case": chosen or case(), "status": "first_attempt_recorded", "wall_s": 1.,
            "setup": [], "first_attempt": {
                "motion_evidence": [{"steps_used": 1}], "physically_executed": True,
                "private_before": {"satisfied": False}, "private_after": {"satisfied": truth},
                "receipt": {"tool": "place", "place_verified": verdict}}}


def files(tmp_path, cases, records, infrastructure_refs=None):
    manifest = tmp_path / "manifest.json"
    plan = {"conditions": {"current160": {"executor": "current", "max_chunks": 160}},
            "cases": cases}
    if infrastructure_refs is not None:
        plan["infrastructure_ledgers"] = infrastructure_refs
    manifest.write_text(json.dumps(plan))
    for record in records:
        directory = tmp_path / record["case"]["name"]
        directory.mkdir()
        trace = directory / "choices.jsonl"
        trace.write_text(json.dumps(record.get("first_attempt")) + "\n")
        record.update(output_dir=str(directory), choices_sha256=summary.sha(trace))
    ledger = tmp_path / "episodes.jsonl"
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records))
    return manifest, ledger


def test_known_truth_agreement_keeps_abstentions_and_unknown_truth_coverage():
    records = [row(truth=truth, verdict=verdict) for truth, verdict in
               [(True, True), (False, False), (True, False), (False, True),
                (True, None), (False, None), (None, True)]]
    report = summary.metrics(records, 10)
    assert report["agreement_over_measured"] == .5  # Legacy metric unchanged.
    assert report["agreement_over_known_private_truth"] == pytest.approx(2 / 6)
    audit = report["verifier_known_truth_audit"]
    assert audit["unknown_private_truth"] == 1
    assert audit["public_unmeasured_on_known_truth"] == 2
    assert audit["rates"]["agreement_over_known_private_truth"]["denominator"] == 6
    assert audit["rates"]["agreement_over_planned_lower_bound"]["denominator"] == 10
    assert audit["rates"]["agreement_over_planned_lower_bound"]["rate"] == .2
    assert audit["rates"]["private_truth_coverage_over_planned"]["rate"] == .6
    assert audit["rates"]["recall_over_known_private_positive_lower_bound"]["rate"] == pytest.approx(1 / 3)
    for key in ("precision", "recall", "false_positive_rate", "false_negative_rate"):
        assert report[key + "_wilson_95CI"] == pytest.approx(summary.wilson(1, 2))
    assert report["public_measurement_coverage_wilson_95CI"] == pytest.approx(summary.wilson(4, 6))


def test_zero_or_unmeasured_evidence_never_creates_perfect_verifier():
    report = summary.metrics([row(verdict=None), row(truth=None, verdict=None)], 3)
    assert report["agreement_over_known_private_truth"] == 0
    assert report["precision"] is None
    assert report["precision_wilson_95CI"] is None
    assert report["verifier_known_truth_audit"]["rates"]["private_truth_coverage_over_planned"]["rate"] == pytest.approx(1 / 3)


def test_raw_sha_uniqueness_is_distinct_from_task_init_and_reset_count(tmp_path):
    cases = [case("a", seed=10), case("b", seed=11), case("c", "b" * 64, 12)]
    manifest, ledger = files(tmp_path, cases, [row(cases[0]), row(cases[1])])
    report = summary.summarize([manifest], [ledger])
    group = report["by_type_condition"]["place_on/current160"]
    assert group["unique_original_initial_states"] == 2
    assert group["unique_raw_initial_state_sha256"] == 1
    assert group["registered_unique_raw_initial_state_sha256"] == 2
    assert group["nominal_registered_resets"] == 3
    assert group["nominal_recorded_resets"] == 2
    assert report["missing_cases"] == ["c"]


def test_infrastructure_rows_are_not_physical_failures():
    failed = {**row(truth=False, verdict=False), "status": "infrastructure_error",
              "infrastructure_failure": True, "eligible_physical_result": False}
    report = summary.metrics([failed, row(truth=False, verdict=False)], 2)
    assert report["counts"]["infrastructure_results_excluded"] == 1
    assert report["first_attempt_executed"] == report["known_truth"] == 1
    assert report["confusion"] == {"tn": 1}
    assert report["failure_counts"] == {"official_predicate_false": 1}
    assert report["verifier_known_truth_audit"]["rates"]["agreement_over_planned_lower_bound"]["rate"] == .5


def test_explicit_attempts_and_case_events_separate_fault_retry_and_recovery(tmp_path, monkeypatch):
    chosen = case()
    initial = {"case": chosen, "attempt_index": 0, "registered_state_sha256": chosen["state_sha256"],
               "status": "infrastructure_error", "infrastructure_failure": True,
               "failure_category": "startup_error"}
    retried = {**row(chosen), "attempt_index": 1, "registered_state_sha256": chosen["state_sha256"],
               "infrastructure_failure": False, "infrastructure_retry": True}
    final = {**retried, "case_had_infrastructure_failure": True,
             "attempts": [{key: attempt[key] for key in ("attempt_index", "registered_state_sha256", "status", "infrastructure_failure")}
                          for attempt in (initial, retried)]}
    # Embedded attempt paths are metadata; the summarizer must not open them.
    final["attempts"][0]["output_dir"] = str(tmp_path / "never_open_attempt_directory")
    manifest, ledger = files(tmp_path, [chosen], [final])
    attempts = tmp_path / "attempts.jsonl"
    attempts.write_text(json.dumps(initial) + "\n" + json.dumps(retried) + "\n")
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"case": chosen["name"], "manifest_sha256": summary.sha(manifest),
                                 "infrastructure_failure": True}) + "\n")
    monkeypatch.setattr(Path, "glob", lambda *_: pytest.fail("directory discovery is forbidden"))
    report = summary.summarize([manifest], [ledger], [attempts, events])
    infra = report["infrastructure"]
    assert report["complete"] is True
    assert report["overall"]["true_successes"] == 1
    assert infra["attempts_recorded"] == 2
    assert infra["counts"] == {"initial_attempts": 1, "infrastructure_failed_attempts": 1,
                               "retry_attempts": 1, "non_infrastructure_attempts": 1}
    assert infra["cases_with_recorded_infrastructure_fault"] == infra["recovered_infrastructure_cases"] == 1
    assert infra["unresolved_infrastructure_cases"] == 0
    assert infra["explicit_attempt_records"] == 2
    assert report["infrastructure_by_type_condition"]["place_on/current160"]["attempts_recorded"] == 2


def test_only_manifest_explicit_infrastructure_reference_is_read_and_hashed(tmp_path):
    attempts = tmp_path / "pinned_attempts.jsonl"
    attempts.write_text(json.dumps({**row(), "attempt_index": 0, "infrastructure_failure": False}) + "\n")
    manifest, ledger = files(tmp_path, [case()], [row()],
                             [{"path": attempts.name, "sha256": summary.sha(attempts)}])
    report = summary.summarize([manifest], [ledger])
    assert report["infrastructure"]["explicit_attempt_records"] == 1
    attempts.write_text(attempts.read_text() + "\n")
    with pytest.raises(ValueError, match="ledger SHA changed"):
        summary.summarize([manifest], [ledger])


def test_missing_explicit_infrastructure_evidence_is_disclosed(tmp_path):
    manifest, ledger = files(tmp_path, [case()], [row()])
    missing = tmp_path / "missing_attempts.jsonl"
    report = summary.summarize([manifest], [ledger], [missing])
    assert report["complete"] is False
    assert report["missing_infrastructure_ledgers"] == [str(missing)]
    assert report["infrastructure"]["legacy_final_rows_assumed_single_attempt"] == 1


def test_grasp_phase_agreement_retains_null_verdict_without_changing_confusion():
    records = [{"status": "recorded", "first_attempt": {"receipt": {"grasp_verified": verdict}},
                "private_grasp_phase": {"true_sustained_grasp_during_skill": True,
                                        "true_sustained_grasp_at_end": True}}
               for verdict in (True, None)]
    report = summary.grasp_phase_metrics(records, 3)
    assert report["runtime_grasp_verifier_against_end_hold"]["agreement"] == 1
    audit = report["runtime_grasp_verifier_known_truth_audit"]
    assert audit["rates"]["agreement_over_known_private_truth"]["rate"] == .5
    assert audit["rates"]["agreement_over_planned_lower_bound"]["rate"] == pytest.approx(1 / 3)
