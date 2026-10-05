"""Endpoint summaries keep native done, unknowns and new achievement separate."""

import pytest

from scripts.summarize_v5_fixture530_closed import confusion, endpoint_metrics, motion_summary, wilson


def test_initially_satisfied_preserved_is_not_a_new_skill_achievement():
    metrics = endpoint_metrics([
        {"transition": "already_satisfied_preserved", "eligible_opposite_start": False,
         "new_requested_from_opposite": False, "after": {"requested": True}},
        {"transition": "new_requested_endpoint", "eligible_opposite_start": True,
         "new_requested_from_opposite": True, "after": {"requested": True}},
        {"transition": "unknown", "eligible_opposite_start": False,
         "new_requested_from_opposite": False, "after": {"requested": None}}])
    assert metrics["recorded_requests"] == 3
    assert metrics["new_endpoint_from_true_opposite"] == metrics["opposite_start_denominator"] == 1
    assert metrics["after_requested_true_including_initially_satisfied"] == 2
    assert metrics["unknown_after_truth"] == 1
    assert metrics["new_endpoint_rate_all_recorded_lower_bound"] == pytest.approx(1 / 3)


def test_unknown_public_verdict_does_not_become_a_false_negative_or_true_negative():
    metrics = confusion([(True, None), (False, None), (True, True), (False, True), (None, False)])
    assert metrics["compared"] == 2
    assert metrics["false_positive"]["count"] == 1
    assert metrics["false_negative"]["count"] == 0
    assert metrics["counts"]["unknown_on_positive_truth"] == 1
    assert metrics["counts"]["unknown_on_negative_truth"] == 1
    assert metrics["counts"]["unknown_truth"] == 1
    assert metrics["agreement"] == .5


def test_full_five_actions_match_scope_even_when_raw_native_success_is_true():
    trace = [{"name": "vla_act_chunk", "requested_action_count": 5, "executed_action_count": 5},
             {"name": "servo", "steps_used": 20}]
    summary = motion_summary(trace, {"requested_controls": 5, "executed_controls": 5,
        "chunks_requested": 1, "raw_native_success_controls": 5, "external_truncation": False})
    assert summary["issues"] == []
    assert summary["executed_vla_controls"] == 5
    assert summary["all_skill_controls_including_motion"] == 25
    assert summary["raw_native_success_controls"] == 5


def test_external_truncation_is_distinct_from_unjustified_native_chunk_loss():
    trace = [{"name": "vla_act_chunk", "requested_action_count": 5, "executed_action_count": 2}]
    scope = {"requested_controls": 5, "executed_controls": 2, "chunks_requested": 1,
             "raw_native_success_controls": 1, "external_truncation": False}
    assert motion_summary(trace, scope)["issues"] == ["nonfive_chunk_without_external_truncation"]
    scope["external_truncation"] = True
    assert motion_summary(trace, scope)["issues"] == []


def test_wilson_reports_the_binomial_uncertainty_without_empty_filled_results():
    assert wilson(0, 0) is None
    assert wilson(10, 10) == pytest.approx([.7224672001371107, 1.])
