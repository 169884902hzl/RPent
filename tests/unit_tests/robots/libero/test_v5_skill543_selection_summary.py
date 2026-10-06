"""Selection reports preserve physical evidence, abstentions and in-flight logs."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import summarize_v5_skill543_selection_20261006 as summary


def case(name="case0", kind="articulate", skill_type="drawer_open", mode="open", seed=10):
    return {"name": name, "kind": kind, "type": skill_type, "mode": mode,
            "condition": "current160", "state_sha256": hashlib.sha256(name.encode()).hexdigest(),
            "episode": {"suite": "libero_90", "task": 6, "seed": seed},
            "object_symbol": "original_object", "setup": []}


def row(chosen, truth=True, verdict=True, before=False):
    key = "place_verified" if chosen["kind"] == "place" else "articulate_verified"
    predicate = {"turn_on": "turnon", "turn_off": "turnoff"}.get(chosen["mode"], chosen["mode"])
    return {"case": chosen, "status": "first_attempt_recorded", "wall_s": 2., "setup": [],
            "first_attempt": {"selected": {"tool": chosen["kind"], "mode": chosen["mode"]},
                "motion_evidence": [{"steps_used": 2}], "physically_executed": True,
                "private_before": {"satisfied": before, "predicate": [predicate, "original_object"],
                                   "joint_qpos": [[.0]]},
                "private_after": {"satisfied": truth, "predicate": [predicate, "original_object"],
                                  "joint_qpos": [[.1]]},
                "receipt": {"tool": chosen["kind"], key: verdict},
                "contact_evidence": {"executed_vla_actions": 2}}}


def files(tmp_path, cases, records):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cohort": "selection", "qualification_authorized": False,
        "new_training_rows": 0, "conditions": {"current160": {"executor": "current", "max_chunks": 160}},
        "cases": cases}))
    for record in records:
        directory = tmp_path / record["case"]["name"]
        directory.mkdir()
        trace = directory / "choices.jsonl"
        trace.write_text(json.dumps(record.get("first_attempt")) + "\n")
        record.update(output_dir=str(directory), choices_sha256=summary.sha(trace))
    ledger = tmp_path / "episodes.jsonl"
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records))
    return manifest, ledger


def test_null_verifier_keeps_known_truth_denominator_and_is_not_false_negative(tmp_path):
    cases = [case("a"), case("b"), case("c")]
    records = [row(cases[0], verdict=None), row(cases[1], truth=False, verdict=True),
               row(cases[2], truth=None, verdict=None)]
    records[0]["first_attempt"]["receipt"].update(verification="unmeasured",
                                                failure_reason="wrist_fixture_handle_not_measured")
    manifest, ledger = files(tmp_path, cases, records)
    report = summary.run_summary(manifest, [ledger], [], tmp_path / "report")
    group = report["by_type_method"][0]
    assert group["private_known"] == 2 and group["private_successes"] == 1
    assert group["confusion"] == {"unmeasured_private_positive": 1, "fp": 1}
    audit = group["known_truth_audit"]
    assert audit["unknown_private_truth"] == 1
    assert audit["rates"]["agreement_over_known_private_truth"]["denominator"] == 2
    assert audit["rates"]["agreement_over_known_private_truth"]["rate"] == 0
    assert audit["rates"]["private_truth_coverage_over_planned"]["denominator"] == 3
    diagnostics = [json.loads(line) for line in (tmp_path / "report/case_diagnostics.jsonl").read_text().splitlines()]
    assert diagnostics[0]["private_truth"] is True
    assert diagnostics[0]["runtime_verified"] is None
    assert diagnostics[0]["unmeasured_reasons"] == ["wrist_fixture_handle_not_measured"]
    assert group["runtime_verified_unmeasured"] == 2


def test_servo_approach_without_vla_contact_has_its_own_evidence_category():
    record = row(case(), truth=False, verdict=None)
    stage = record["first_attempt"]
    stage["contact_evidence"]["executed_vla_actions"] = 0
    stage["receipt"].update(fixture_handle_approach={"ready_for_contact": False,
        "before": {"ready": True}, "after_wrist_refinement": {"reason": "not_measured"},
        "waypoints": [{"final_dist_m": .01}]}, failure_reason="wrist_fixture_handle_not_measured")
    diagnostic = summary.case_diagnostic(record | {"output_dir": "explicit_case"}, {"max_chunks": 160})
    assert diagnostic["first_skill_physically_executed"] is True
    assert diagnostic["contact_physically_executed"] is False
    assert diagnostic["root_cause_category"] == "measured_approach_not_ready_contact_not_executed"
    assert diagnostic["private_truth"] is False
    assert diagnostic["measured_approach_waypoints"] == [{"final_dist_m": .01}]
    stage["contact_evidence"].pop("executed_vla_actions")
    diagnostic = summary.case_diagnostic(record | {"output_dir": "explicit_case"}, {"max_chunks": 160})
    assert diagnostic["contact_physically_executed"] is None
    assert diagnostic["root_cause_category"] == "requested_endpoint_not_reached"


def test_infrastructure_attempt_retry_is_counted_separately_from_physical_failure(tmp_path):
    chosen = case()
    initial = {"case": chosen, "attempt_index": 0, "registered_state_sha256": chosen["state_sha256"],
               "status": "infrastructure_error", "infrastructure_failure": True,
               "failure_category": "startup_error"}
    retried = {**row(chosen), "attempt_index": 1, "registered_state_sha256": chosen["state_sha256"],
               "infrastructure_failure": False, "infrastructure_retry": True}
    final = {**retried, "case_had_infrastructure_failure": True,
             "attempts": [{key: attempt[key] for key in ("attempt_index", "registered_state_sha256", "status", "infrastructure_failure")}
                          for attempt in (initial, retried)]}
    manifest, ledger = files(tmp_path, [chosen], [final])
    attempts = tmp_path / "attempts.jsonl"
    attempts.write_text(json.dumps(initial) + "\n" + json.dumps(retried) + "\n")
    report = summary.run_summary(manifest, [ledger], [attempts], tmp_path / "report")
    group = report["by_type_method"][0]
    assert report["complete"] is True and group["private_successes"] == 1
    assert group["physical_first_attempts"] == 1 and group["infrastructure_fault_cases"] == 1
    assert group["unresolved_infrastructure_cases"] == 0
    assert group["attempts"]["attempts_recorded"] == 2
    assert group["root_cause_counts"] == {"newly_satisfied": 1}


def test_unresolved_infrastructure_is_unavailable_not_physical_false(tmp_path):
    chosen = case()
    failed = {**row(chosen, truth=False, verdict=False), "status": "infrastructure_error",
              "infrastructure_failure": True, "eligible_physical_result": False}
    manifest, ledger = files(tmp_path, [chosen], [failed])
    report = summary.run_summary(manifest, [ledger], [], tmp_path / "report")
    group = report["by_type_method"][0]
    assert group["private_known"] == group["physical_first_attempts"] == 0
    assert group["confusion"] == {}
    assert group["runtime_verified_false"] == 0
    assert group["unresolved_infrastructure_cases"] == 1
    assert group["root_cause_counts"] == {"infrastructure_unavailable": 1}


def test_prepared_empty_summary_lists_all_six_fixture_types_without_discovery(tmp_path, monkeypatch):
    operations = [("drawer_open", "open"), ("drawer_close", "close"), ("microwave_open", "open"),
                  ("microwave_close", "close"), ("stove_turn_on", "turn_on"), ("stove_turn_off", "turn_off")]
    cases = [case(skill_type, skill_type=skill_type, mode=mode) for skill_type, mode in operations]
    manifest, ledger = files(tmp_path, cases, [])
    def forbidden(*args, **kwargs):
        pytest.fail("directory discovery is forbidden")
    for name in ("glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    report = summary.run_summary(manifest, [], [], tmp_path / "report")
    assert report["complete"] is False
    assert len(report["by_type_method"]) == 6
    assert report["overall"]["planned"] == report["overall"]["missing"] == 6
    assert all(group["completed_case_records"] == 0 and group["private_known"] == 0
               for group in report["by_type_method"])
    assert report["qualification_authorized"] is False
    assert report["new_training_rows"] == report["new_physical_trials"] == 0


def test_active_ledger_tail_is_saved_without_touching_input_or_scoring_partial_case(tmp_path):
    a, b = case("a"), case("b")
    manifest, ledger = files(tmp_path, [a, b], [row(a)])
    tail = b'{"case":{"name":"b"'
    ledger.write_bytes(ledger.read_bytes() + tail)
    original = ledger.read_bytes()
    report = summary.run_summary(manifest, [ledger], [], tmp_path / "report")
    assert ledger.read_bytes() == original
    assert report["complete"] is False and report["overall"]["recorded"] == 1
    assert report["missing_cases"] == ["b"]
    evidence = report["deferred_inflight_tails"][0]
    assert evidence["captured_sha256"] == hashlib.sha256(original).hexdigest()
    assert Path(evidence["deferred_tail"]).read_bytes() == tail
    assert evidence["deferred_tail_bytes"] == len(tail)


def test_completed_selection_distinguishes_preserved_from_new_endpoint_and_never_qualifies(tmp_path):
    a, b = case("a"), case("b")
    manifest, ledger = files(tmp_path, [a, b], [row(a, before=True), row(b)])
    report = summary.run_summary(manifest, [ledger], [], tmp_path / "report", source_commit="e50e474", job_ids=["4094"])
    group = report["by_type_method"][0]
    assert report["complete"] is True
    assert group["private_successes"] == 2 and group["private_newly_satisfied"] == 1
    assert group["private_already_satisfied_before"] == 1
    assert group["root_cause_counts"] == {"already_satisfied_preserved": 1, "newly_satisfied": 1}
    assert report["qualification_authorized"] is False
    assert report["job_ids"] == ["4094"] and report["source"]["commit"] == "e50e474"


@pytest.mark.parametrize("changed", ["case", "trace"])
def test_registered_case_and_trace_identity_are_checked(tmp_path, changed):
    chosen = case()
    record = row(chosen)
    manifest, ledger = files(tmp_path, [chosen], [record])
    if changed == "case":
        record["case"]["mode"] = "close"
        ledger.write_text(json.dumps(record) + "\n")
    else:
        (Path(record["output_dir"]) / "choices.jsonl").write_text("changed\n")
    with pytest.raises(ValueError, match="unregistered|trace SHA"):
        summary.run_summary(manifest, [ledger], [], tmp_path / "report")


@pytest.mark.parametrize("key,value", [("cohort", "confirmation"), ("qualification_authorized", True),
                                       ("new_training_rows", 1)])
def test_nonselection_or_training_manifest_cannot_be_summarized_as_selection(tmp_path, key, value):
    manifest, ledger = files(tmp_path, [case()], [])
    plan = json.loads(manifest.read_text())
    plan[key] = value
    manifest.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="selection manifest required"):
        summary.run_summary(manifest, [], [], tmp_path / "report")
