"""Completion diagnosis cannot change action selection or hide API failures."""

import io
import json
from urllib.error import HTTPError

import pytest

from robots.libero import v5_systemone
from typed_choice_eval import ChoiceScorer


def response(*, done=0.99, compute=True):
    result = {"model": "local-test-checkpoint", "answers": {
        "action": {"choice": "C1", "probabilities": {"C0": .1, "C1": .9}},
        "goal_done": {"noul": done},
    }}
    if compute:
        result["timing_ms"] = {"compute": 125}
    return result


def test_same_request_high_done_does_not_override_selected_non_finish(monkeypatch):
    received = []
    def send(request, timeout):
        received.append((request.full_url, json.loads(request.data)))
        return io.BytesIO(json.dumps(response()).encode())
    monkeypatch.setattr(v5_systemone, "urlopen", send)
    scorer = ChoiceScorer("systemone", "http://localhost:19120/v1/systemone",
                          goal_done_diagnostic=True)
    result = scorer.score("instruction move the bowl\ne e1 src=perception", "Choose", ["finish()", "grasp(e1,direct)"])
    assert len(received) == 1
    assert received[0][0] == "http://localhost:19120/v1/systemone"
    assert set(received[0][1]["questions"]) == {"action", "goal_done"}
    assert result["selected"] == 1
    assert result["goal_done_diagnostic"] == {
        "p_done": .99, "state_time": "before_action", "behavior_changed": False}
    assert result["model_inference_s"] == .125
    assert result["http_round_trip_s"] >= 0


def test_http_latency_is_not_fabricated_server_compute():
    result = v5_systemone.parse_answer(response(compute=False), 2, goal_done=True, http_s=.42)
    assert result["model_inference_s"] is None
    assert result["http_round_trip_s"] == .42


@pytest.mark.parametrize("bad", [-.1, 1.1, float("nan")])
def test_malformed_done_probability_is_rejected(bad):
    with pytest.raises(ValueError, match="p\\(done\\)"):
        v5_systemone.parse_answer(response(done=bad), 2, goal_done=True, http_s=.1)


def test_token_rejection_is_preserved_without_retry_or_truncation(monkeypatch):
    requests = []
    def send(request, timeout):
        requests.append(json.loads(request.data))
        raise HTTPError(request.full_url, 422, "over token", {}, io.BytesIO(b'3072 hard limit'))
    monkeypatch.setattr(v5_systemone, "urlopen", send)
    with pytest.raises(RuntimeError, match="3072 hard limit"):
        v5_systemone.score("http://localhost", "state " * 4000, "Choose", ["finish()"], goal_done=True)
    assert len(requests) == 1
    assert requests[0]["state"] == "state " * 4000


def test_diagnostic_off_omits_completion_question():
    assert set(v5_systemone.questions("Choose", ["finish()"], goal_done=False)) == {"action"}


def test_media_opt_in_preserves_text_and_default_wire(monkeypatch):
    received = []
    def send(request, timeout):
        received.append(json.loads(request.data))
        return io.BytesIO(json.dumps(response()).encode())
    monkeypatch.setattr(v5_systemone, "urlopen", send)
    scorer = ChoiceScorer("systemone", "http://localhost")
    context = "instruction move the bowl\ne e37 src=perception"
    scorer.score(context, "Choose", ["finish()", "grasp(e37,direct)"])
    media = {"images": [{"view": "agentview", "mime_type": "image/png", "data": "AA=="},
                        {"view": "wrist", "mime_type": "image/png", "data": "AA=="}]}
    scorer.score(context, "Choose", ["finish()", "grasp(e37,direct)"], media=media)
    assert "media" not in received[0]
    assert received[1].pop("media") == media
    assert received[1] == received[0]
