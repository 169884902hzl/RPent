import pytest

from scripts.compare_v5_A2M_A1M_20261003 import compare, receipt_counts
from scripts.summarize_v5_A3_step750_20261003 import measured_timing


def episode(task):
    return {"suite": "libero_object_swap", "task": task, "seed": 40}


def row(task, success, baseline=False, status="completed"):
    result = {"official_success": success, "status": status, "wall_s": 10,
              "termination_category": "success" if success else "budget_exhausted"}
    return {"episode": episode(task), "output_dir": "/test/" + str(task),
            **(result if baseline else {"result": result})}


def test_missing_development_run_is_not_filled_with_failure():
    expected = {(e["suite"], e["task"], e["seed"]) for e in [episode(0), episode(1)]}
    report = compare([row(0, True, True), row(1, True, True)], [row(0, True)], expected)
    assert report["complete"] is False
    assert report["A2_M"]["recorded"] == 1
    assert report["paired"] == {"both_success": 1}
    assert len(report["missing_A2_M"]) == 1


def test_infrastructure_pair_is_separate_from_model_regression():
    expected = {("libero_object_swap", 0, 40)}
    report = compare([row(0, True, True)], [row(0, False, status="startup_error")], expected)
    assert report["paired"] == {"infrastructure_pair": 1}
    assert report["valid_pairs"] == 0
    assert report["A2_M"]["valid_model_episodes"] == 0
    assert report["paired_success_delta_pp"] is None


def test_raw_original_api_terminal_is_preserved_and_startup_is_not_a_model_result():
    expected = {("libero_object_swap", 0, 40)}
    baseline = row(0, False, True)
    baseline["termination_category"] = "infrastructure_error"
    report = compare([baseline], [row(0, False)], expected)
    assert report["A1_M"]["terminal_categories"] == {"infrastructure_error": 1}
    assert report["A1_M"]["valid_model_episodes"] == 0
    assert report["paired"] == {"infrastructure_pair": 1}


@pytest.mark.parametrize("unregistered", [False, True])
def test_duplicate_and_outside_cohort_ledgers_are_rejected(unregistered):
    expected = {("libero_object_swap", 0, 40)}
    rows = [row(1, True)] if unregistered else [row(0, True), row(0, True)]
    with pytest.raises(ValueError, match="duplicate or unregistered"):
        compare([row(0, True, True)], rows, expected)


def test_help_after_failed_grasp_is_not_perception_failure():
    result = receipt_counts([
        {"receipt": {"tool": "grasp", "grasp_verified": False}},
        {"receipt": {"tool": "ask_help", "verification": "help_unavailable"}},
        {"receipt": {"tool": "place", "verification": "execution_error", "error": "ValueError"}},
    ])
    assert result["receipt_events"]["help_after_failed_grasp"] == 1
    assert result["receipt_events"]["execution_error"] == 1
    assert "perception_missing_object" not in result["receipt_events"]


@pytest.mark.parametrize("kind,field", [("http_round_trip", "http_round_trip"),
                                        ("server_compute", "model_inference")])
def test_recorded_decision_latency_keeps_its_measured_kind(kind, field):
    event = {"timing_s": {"decision_inference": .3, "decision_inference_kind": kind,
                          "http_round_trip": None, "model_inference": None}}
    timing = measured_timing(event)
    assert timing[field] == .3
    other = "model_inference" if field == "http_round_trip" else "http_round_trip"
    assert timing[other] is None
    assert event["timing_s"][field] is None


def test_server_computation_is_not_overwritten_by_transport_or_an_unknown_alias():
    timing = measured_timing({"timing_s": {"decision_inference": .3,
        "decision_inference_kind": "http_round_trip", "model_inference": .2}})
    assert timing["model_inference"] == .2 and timing["http_round_trip"] == .3
    timing = measured_timing({"timing_s": {"decision_inference": .3}})
    assert "model_inference" not in timing and "http_round_trip" not in timing
