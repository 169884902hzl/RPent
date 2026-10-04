"""Recorded-prefix diagnosis preserves native completion and infeasible suffixes."""

from scripts.replay_v5_original_motion import ReplaySelectionUnavailable, prefix_outcome


def test_native_success_before_the_last_recorded_action_is_not_a_runtime_failure():
    assert prefix_outcome(1, 2, {"official_success": True, "native_terminated": True}, None) == "native_success"


def test_missing_suffix_after_fresh_grasp_failure_is_physical_divergence():
    error = ReplaySelectionUnavailable("recorded place is unavailable")
    assert prefix_outcome(1, 2, {"official_success": False}, error) == "physical_precondition_divergence"


def test_environment_error_is_retained_as_runtime_failure():
    assert prefix_outcome(0, 2, {}, RuntimeError("environment unavailable")) == "runtime_error"


def test_short_unsolved_execution_remains_incomplete():
    assert prefix_outcome(1, 2, {"official_success": False}, None) == "incomplete_prefix"


def test_executed_prefix_is_distinct_from_full_task_success():
    assert prefix_outcome(2, 2, {"official_success": False}, None) == "complete_prefix"
