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
