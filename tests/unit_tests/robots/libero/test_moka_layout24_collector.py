import json

import pytest

from scripts.collect_moka_layout24 import collect, reference


def inputs(tmp_path, rows):
    cases = [{"name": f"layout{i}", "state_sha256": f"state{i}",
              "geometry_fingerprint": f"geometry{i}"} for i in range(24)]
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"cases": cases}))
    ledger = tmp_path / "episodes.jsonl"
    ledger.write_text("".join(json.dumps({"case": cases[i], **row}) + "\n"
                              for i, row in enumerate(rows)))
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"plan": reference(plan), "ledgers": [
        {"job_id": "confirmation", "path": str(ledger)}]}))
    return registry


def success():
    return {"official_subtask_success": True,
            "private_original_task_status_after": {"done": True},
            "public_placement_verdict": True,
            "server_chunk_execution": {"executed_controls": 5, "requested_controls": 5},
            "chunks": 1, "wall_s": 1,
            "result": {"official_success": True}}


def test_no_execution_binding_failure_stays_in_denominator_with_unknown_truth(tmp_path):
    missing = {"official_subtask_success": None, "private_original_task_status_after": None,
               "public_placement_verdict": None, "server_chunk_execution": None,
               "first_receipt": {"executed": False, "failure_reason": "binding_missing"},
               "executed_vla_actions": 0, "executed_public_motion_actions": 0,
               "chunks": 0, "wall_s": .5, "result": {"official_success": False}}
    result = collect(inputs(tmp_path, [success(), missing]), tmp_path / "output")
    summary = result["summary"]
    assert summary["completed"] == 2
    assert summary["transfer_rate"] == .5
    assert summary["private_truth_unknown"] == 1
    assert summary["paired_labels_known"] == summary["agreement_known"] == 1
    assert summary["false_positive"] == summary["false_negative"] == 0
    assert summary["outcomes"]["no_execution"] == 1
    report = json.loads((tmp_path / "output/report.json").read_text())
    assert report["rows"][1]["simulation_final_transfer"] is None


def test_inconsistent_known_private_labels_are_rejected(tmp_path):
    row = success()
    row["private_original_task_status_after"]["done"] = False
    with pytest.raises(ValueError, match="inconsistent"):
        collect(inputs(tmp_path, [row]), tmp_path / "output")


def test_infrastructure_attempt_is_separate_and_not_a_skill_failure(tmp_path):
    row = {**success(), "case_had_infrastructure_failure": True, "error": "RpcError"}
    summary = collect(inputs(tmp_path, [row]), tmp_path / "output")["summary"]
    assert summary["infrastructure_attempts"] == 1
    assert summary["completed"] == 0
    assert summary["transfer_rate"] is None


def test_union100_keeps_preparation_invalid_and_pending_separate(tmp_path):
    registry_path = inputs(tmp_path, [success()])
    registry = json.loads(registry_path.read_text())
    cases = [{"name": f"layout{i}", "state_sha256": f"state{i}",
              "geometry_fingerprint": f"geometry{i}"} for i in range(24, 100)]
    plan76 = tmp_path / "plan76.json"
    plan76.write_text(json.dumps({"cases": cases}))
    ledger76 = tmp_path / "episodes76.jsonl"
    ledger76.write_text(json.dumps({"case": cases[1], **success()}) + "\n")
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(["layout24", "layout74"]))
    cases24 = json.loads((tmp_path / "plan.json").read_text())["cases"]
    permanent = tmp_path / "permanent.json"
    permanent.write_text(json.dumps({"training_allowed": False, "records": [
        {"case_name": c["name"], "state_sha256": c["state_sha256"],
         "geometry_fingerprint": c["geometry_fingerprint"], "permanent_training_exclusion": True}
        for c in cases24 + cases]}))
    registry.update(planned=100, plans=[registry.pop("plan"), reference(plan76)],
                    preparation_invalid_cases=reference(invalid),
                    permanent_exclusion_registry=reference(permanent))
    registry["ledgers"].append({"job_id": "additional76", "path": str(ledger76)})
    registry_path.write_text(json.dumps(registry))
    summary = collect(registry_path, tmp_path / "output")["summary"]
    assert summary["planned"] == 100
    assert summary["valid_preparations"] == 98
    assert summary["preparation_invalid"] == 2
    assert summary["completed"] == 2
    assert summary["remaining"] == 96
    assert summary["transfer_rate"] == 1
    assert summary["demonstrated_success_over_registered"] == .02
    assert summary["cohorts"]["approved24"]["completed"] == 1
    assert summary["cohorts"]["additional76"]["preparation_invalid"] == 2
