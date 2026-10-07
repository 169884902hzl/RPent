"""Opt-in public temporal endpoint stopping keeps legacy contacts unchanged."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity
from robots.libero.v5_temporal_verifier import feature_encoder_identity, infer, public_frame


def _primitive():
    primitive = SimpleNamespace(
        _last_obs_gripper=.04,
        _last_obs_eef_pos=np.array([0., 0., 1.]),
        env=SimpleNamespace(terminated=False, truncated=False),
    )
    primitive._vlm_chunk = lambda prompt: None
    return primitive


def test_vla_act_accepts_admitted_temporal_evidence_and_stops_immediately():
    calls = []
    primitive = _primitive()
    primitive._vlm_chunk = lambda prompt: calls.append(prompt)
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace())

    def callback(chunks):
        return {"status": "predicted", "stop_admitted": chunks == 2,
                "stop_reason": "temporal_endpoint_verified", "p_satisfied": .99}

    result = executor.vla_act("turn on the stove", 20, "chunk_budget", public_stop=callback)
    assert len(calls) == 2
    assert result["stop"] == "temporal_endpoint_verified"
    assert result["temporal_endpoint"]["p_satisfied"] == .99


def test_vla_act_does_not_treat_unknown_temporal_evidence_as_truthy_stop():
    calls = []
    primitive = _primitive()
    primitive._vlm_chunk = lambda prompt: calls.append(prompt)
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace())
    result = executor.vla_act(
        "turn on the stove", 4, "chunk_budget",
        public_stop=lambda chunks: {"status": "unknown", "stop_admitted": False},
    )
    assert len(calls) == 4
    assert result["stop"] == "chunk_budget"
    assert "temporal_endpoint" not in result


def test_temporal_callback_is_opt_in_and_keeps_public_evidence(monkeypatch):
    from robots.libero import v5_temporal_verifier

    events = []

    class FakeVerifier:
        def __init__(self, *args, **kwargs):
            events.append(("init", args[1]))
            assert kwargs == {"requested_mode": "turn_on"}
            self.records = []

        def start(self):
            events.append("start")

        def observe(self, chunks):
            evidence = {"status": "predicted", "stop_admitted": chunks == 3,
                        "p_satisfied": .97, "chunk": chunks}
            self.records.append(evidence)
            return evidence

    monkeypatch.setattr(v5_temporal_verifier, "TemporalEndpointVerifier", FakeVerifier)
    parent = Entity("e1", "stove", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.1))
    executor = V5Executor(
        SimpleNamespace(primitives=_primitive()), SimpleNamespace(),
        temporal_endpoint_stop_v1=True,
        temporal_endpoint_model_path="/tmp/registered_temporal_model.npz",
        temporal_endpoint_threshold_v1=.9,
    )
    callback = executor.temporal_endpoint_public_stop(parent, "stove", "turn_on")
    assert callback(2) is False
    assert callback(3)["stop_admitted"] is True
    assert executor.last_verification_measurements["temporal_endpoint_stop"][-1]["chunk"] == 3
    assert events[0][0] == "init" and events[1] == "start"


def test_public_frame_with_missing_artifacts_abstains_without_private_values():
    executor = SimpleNamespace(
        toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=None)),
        p=SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.]), _last_obs_gripper=.04),
    )
    frame = public_frame(executor, {"lower": [-.1, -.1, .9], "upper": [.1, .1, 1.1]})
    assert frame["available"] == [False, False]
    assert frame["private_object_or_joint_values"] is False


def test_infer_only_admits_with_explicit_threshold(tmp_path):
    model = tmp_path / "model.npz"
    np.savez(
        model,
        mean=np.zeros(2), scale=np.ones(2),
        output_weight=np.array([1., 1.]), output_bias=np.array(2.),
        supports_modes=np.asarray(["turn_off"]),
        feature_encoder_sha256=np.asarray(feature_encoder_identity()),
    )
    without = infer(np.ones(2), [True, False], model, requested_mode="turn_off")
    with_threshold = infer(np.ones(2), [True, False], model, threshold=.9, requested_mode="turn_off")
    assert without["status"] == "predicted"
    assert without["stop_admitted"] is False
    assert with_threshold["stop_admitted"] is True


def test_turn_off_model_cannot_stop_turn_on_or_unknown_action(tmp_path):
    model = tmp_path / "turn_off.npz"
    np.savez(model, mean=np.zeros(2), scale=np.ones(2), output_weight=np.ones(2), output_bias=np.array(50.),
             supports_modes=np.asarray(["turn_off"]), feature_encoder_sha256=np.asarray(feature_encoder_identity()))
    for mode in (None, "turn_on", "open"):
        result = infer(np.ones(2), [True, True], model, threshold=.5, requested_mode=mode)
        assert result["status"] == "unknown" and result["stop_admitted"] is False
        assert result["reason"] == "temporal_model_mode_not_supported"


def test_old_or_different_encoder_model_cannot_authorize_a_stop(tmp_path):
    for metadata in ({}, {"supports_modes": np.asarray(["turn_off"]),
                           "feature_encoder_sha256": np.asarray("different_encoder")}):
        model = tmp_path / "model.npz"
        np.savez(model, mean=np.zeros(2), scale=np.ones(2), output_weight=np.ones(2), output_bias=np.array(50.),
                 **metadata)
        result = infer(np.ones(2), [True, True], model, threshold=.5, requested_mode="turn_off")
        assert result["status"] == "unknown" and result["stop_admitted"] is False


@pytest.mark.parametrize("tool", ["articulate", "vla_subtask"])
def test_stove_stop_preserves_the_following_state_refresh(tool):
    stove = Entity("e1", "stove", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.1))
    scene = SimpleNamespace(entities={stove.id: stove}, fixture_handle_geometry_v3=False,
                            view_axes=((1., 0., 0.), (0., 1., 0.)))
    calls = []
    primitive = _primitive()
    primitive._vlm_chunk = lambda prompt: calls.append("chunk")
    executor = V5Executor(SimpleNamespace(primitives=primitive), scene,
                          temporal_endpoint_stop_v1=True, temporal_endpoint_model_path="test_model.npz",
                          temporal_endpoint_threshold_v1=.9)
    executor.measure_stove = lambda parent: {"state": "on"}
    executor.verify_stove = lambda *args: (None, {"state": "unmeasured"})
    executor.temporal_endpoint_public_stop = lambda *args: lambda chunks: {
        "stop_admitted": chunks == 2, "stop_reason": "temporal_endpoint_verified"}
    executor._refresh = lambda names: calls.append("refresh")
    receipt = {}
    action = Candidate(tool, stove.id, mode="turn_off")
    if tool == "articulate":
        executor._execute(action, receipt, None)
    else:
        executor.execute_subtask(action, receipt)
    assert calls == ["chunk", "chunk", "refresh"]
    assert receipt["stop"] == "temporal_endpoint_verified"
    assert receipt["verification"] == "unmeasured"
