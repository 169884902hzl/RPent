"""Success scores change only the authorized physical development choice."""

from robots.libero import v5_success_choice


def answer(selected=0):
    return {"selected": selected, "probabilities": {"C0": .6, "C1": .3, "C2": .1},
            "http_round_trip_s": .2, "model_inference_s": .15}


def test_grasp_reranking_keeps_original_distribution_and_prestate(monkeypatch):
    calls = []
    def score(endpoint, context, action):
        calls.append((context, action))
        probability = [.1, .9][len(calls) - 1]
        return {"p_success": probability,
                "http_round_trip_s": .1, "model_inference_s": .08}
    monkeypatch.setattr(v5_success_choice, "predict_success", score)
    original = answer()
    result = v5_success_choice.rerank_grasp("http://localhost", "saved pre-state", ["grasp(e3,direct)", "grasp(e3,above_10cm)", "finish()"], original)
    assert result["selected"] == 1
    assert result["probabilities"] == original["probabilities"]
    assert original["selected"] == 0
    assert all(context == "saved pre-state" for context, _ in calls)
    assert result["http_round_trip_s"] == .4


def test_place_and_terminal_choices_do_not_use_unsupported_predictions(monkeypatch):
    def unexpected(*args):
        raise AssertionError("unsupported success prediction")
    monkeypatch.setattr(v5_success_choice, "predict_success", unexpected)
    for options in (["place(e3,e8,on)", "grasp(e3,direct)", "finish()"], ["finish()", "grasp(e3,direct)", "grasp(e8,direct)"]):
        original = answer()
        assert v5_success_choice.rerank_grasp("http://localhost", "pre", options, original) is original


def test_online_diagnosis_scores_executed_action_without_reranking(monkeypatch):
    import hashlib
    import pytest

    calls = []
    def score(endpoint, context, action):
        calls.append((context, action))
        return {"p_success": .08, "http_round_trip_s": .1, "model_inference_s": .06}
    monkeypatch.setattr(v5_success_choice, "predict_success", score)
    original = answer(selected=1)
    context = 'instruction place the bowl\nreceipt {"grasp_verified":false}'
    result = v5_success_choice.diagnose_selected_success("http://localhost", context,
        ["grasp(e3,direct)", "grasp(e3,above_10cm)", "finish()"], original)
    assert calls == [(context, "grasp(e3,above_10cm)")]
    assert result["selected"] == original["selected"] == 1
    assert result["probabilities"] == original["probabilities"]
    diagnostic = result["pre_action_success_diagnostic"]
    assert diagnostic["phase"] == "before_physical_branches_and_execution"
    assert diagnostic["context_sha256"] == hashlib.sha256(context.encode()).hexdigest()
    assert diagnostic["selection_changed"] is False
    assert diagnostic["p_success"] == .08
    assert "pre_action_success_diagnostic" not in original
    assert result["model_inference_s"] == pytest.approx(.21)


def test_online_diagnosis_keeps_missing_server_compute_unknown(monkeypatch):
    monkeypatch.setattr(v5_success_choice, "predict_success", lambda *a: {
        "p_success": .9, "http_round_trip_s": .1, "model_inference_s": None})
    result = v5_success_choice.diagnose_selected_success("http://localhost", "pre", ["grasp(e3,direct)"], answer())
    assert result["model_inference_s"] is None
