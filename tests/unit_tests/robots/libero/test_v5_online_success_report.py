"""Only matching online predictions and known physical outcomes are scored."""

import copy

import pytest

from robots.libero import v5_success_choice
from scripts.summarize_v5_online_success import executed_prediction, summarize


def event(monkeypatch):
    context, action = "instruction pick up the bowl", "grasp(e7,direct)"
    def prediction(endpoint, state, selected):
        return {"p_success": .9, "request": v5_success_choice.success_payload(state, selected),
                "response": {"answers": {"success": {"probabilities": {"C0": .1, "C1": .9}}}},
                "http_round_trip_s": .2, "model_inference_s": .1}
    monkeypatch.setattr(v5_success_choice, "predict_success", prediction)
    answer = v5_success_choice.diagnose_selected_success("unused", context, [action],
        {"selected": 0, "probabilities": {"C0": .01}, "http_round_trip_s": .1,
         "model_inference_s": .05})
    return {"request": {"context": context}, "answer": answer, "selected": action,
            "candidates": [action], "decision": 3,
            "receipt": {"tool": "grasp", "grasp_verified": False}}


def test_reports_independent_prediction_and_actual_physical_failure(monkeypatch):
    row, excluded = executed_prediction(event(monkeypatch))
    assert excluded is None
    assert row["p_success"] == .9  # Action-choice confidence is only .01.
    assert row["actual_success"] == 0
    report = summarize([{**row, "episode_key": "same episode"}], 471)
    assert report["AUROC"] is None
    assert report["episode_bootstrap_AUROC_95CI"] is None
    assert report["high_confidence_error_rate"] == 1


@pytest.mark.parametrize("mutation", ["context", "action", "retrospective", "probability"])
def test_rejects_prediction_from_a_different_execution(monkeypatch, mutation):
    saved = copy.deepcopy(event(monkeypatch))
    if mutation == "context":
        saved["request"]["context"] += " changed state"
    elif mutation == "action":
        saved["selected"] = "grasp(e8,direct)"
    elif mutation == "retrospective":
        saved["answer"]["pre_action_success_diagnostic"]["phase"] = "after_execution"
    else:
        saved["answer"]["pre_action_success_diagnostic"]["p_success"] = .2
    with pytest.raises(ValueError):
        executed_prediction(saved)


def test_unverified_action_is_excluded_instead_of_counted_as_failure(monkeypatch):
    saved = event(monkeypatch)
    saved["receipt"] = {"tool": "grasp", "grasp_verified": None, "verification": "unverified"}
    assert executed_prediction(saved) == (None, "unknown_or_unverified")


def test_old_trace_without_online_scores_does_not_become_online_evidence(monkeypatch):
    saved = event(monkeypatch)
    saved["answer"].pop("pre_action_success_diagnostic")
    assert executed_prediction(saved) == (None, "no_online_prediction")


def test_episode_bootstrap_keeps_perfect_ranking_at_one():
    rows = [{"episode_key": episode, "p_success": score, "actual_success": label}
            for episode in ("a", "b") for score, label in ((.1, 0), (.9, 1))]
    report = summarize(rows, 471)
    assert report["AUROC"] == 1
    assert report["episode_bootstrap_AUROC_95CI"] == [1, 1]


def test_empty_scores_have_unknown_calibration():
    report = summarize([], 471)
    assert report["AUROC"] is None
    assert report["Brier"] is None
    assert report["ECE10"] is None


@pytest.mark.parametrize("target,verdict", [("e8", True), (None, False), ("e8", None)])
def test_online_complete_subtask_uses_its_actual_measurement(monkeypatch, target, verdict):
    saved = event(monkeypatch)
    action = "vla_subtask(e7,e8,in)" if target else "vla_subtask(e7,open)"
    saved["selected"] = action
    saved["candidates"] = [action]
    diagnostic = saved["answer"]["pre_action_success_diagnostic"]
    diagnostic["candidate"] = action
    diagnostic["prediction"]["request"] = v5_success_choice.success_payload(saved["request"]["context"], action)
    saved["receipt"] = {"tool": "vla_subtask", "target": target,
                        "place_verified" if target else "articulate_verified": verdict}
    row, reason = executed_prediction(saved)
    if verdict is None:
        assert row is None and reason == "unknown_or_unverified"
    else:
        assert reason is None and row["actual_success"] == int(verdict)
