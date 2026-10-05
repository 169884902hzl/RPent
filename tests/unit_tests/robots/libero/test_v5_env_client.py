"""Placement may finish its visual receipt after native success, within budget."""

import numpy as np
import pytest

from robots.libero.v5_env_client import V5SkillEnvClient


class FakeEnvRpc:
    def __init__(self):
        self.steps = 0
        self.truncates = False

    def call(self, method, **kwargs):
        if method == "env.get_env_meta":
            return {"task": 0}
        if method == "env.reset":
            return {"step": 0}, {}
        assert method == "env.step"
        self.steps += 1
        return {"step": self.steps}, 1, np.array([True]), np.array([self.truncates]), {}


def test_success_latch_survives_release_and_retreat_until_explicit_finish():
    rpc = FakeEnvRpc()
    client = V5SkillEnvClient(rpc, expected_meta={"task": 0})
    with client.complete_skill():
        client.step(np.zeros(7))
        assert not client.terminated
        client.step(np.zeros(7))
        assert not client.terminated
    assert client.terminated and not client.truncated
    assert rpc.steps == 2
    with pytest.raises(AssertionError):
        client.step(np.zeros(7))
    client.reset()
    assert not client.terminated and not client.truncated


def test_budget_truncation_stops_placement_and_exception_keeps_native_success():
    rpc = FakeEnvRpc()
    client = V5SkillEnvClient(rpc, expected_meta={"task": 0})
    with pytest.raises(AssertionError), client.complete_skill():
        rpc.truncates = True
        client.step(np.zeros(7))
        assert client.truncated
        client.step(np.zeros(7))
    assert client.terminated and client.truncated
    assert rpc.steps == 1


@pytest.mark.parametrize("enabled,steps", [(False, 2), (True, 1)])
@pytest.mark.parametrize("tool", ["grasp", "regrasp_restage", "card_next"])
def test_native_grasp_stop_prevents_a_trial_lift_after_task_completion(enabled, steps, tool):
    from types import SimpleNamespace

    from robots.libero.v5_runtime import V5Executor
    from robots.libero.v5_state import Candidate

    rpc = FakeEnvRpc()
    client = V5SkillEnvClient(rpc, expected_meta={"task": 0})
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace(env=client)),
                          SimpleNamespace(), native_grasp_stop_v1=enabled)
    executor.capture = lambda: None

    def contact_then_trial_lift(action, receipt, card):
        client.step(np.zeros(7))
        if not client.terminated:
            client.step(np.zeros(7))
        receipt["executed"] = True

    executor._execute = contact_then_trial_lift
    card = {"selector": {"skill": "grasp"}} if tool == "card_next" else None
    receipt = executor.execute(Candidate(tool, "e1"), card=card)
    assert client.terminated and not client.truncated
    assert receipt["executed"] and not receipt.get("error")
    assert rpc.steps == steps


class MetaEnvRpc(FakeEnvRpc):
    def __init__(self, meta):
        super().__init__()
        self.meta = meta

    def call(self, method, **kwargs):
        if method == "env.get_env_meta":
            return self.meta
        return super().call(method, **kwargs)


def test_original90_connector_carries_diagnostic_identity_and_preserves_input():
    expected = {"suite": "libero_90", "task": 7, "seed": 13, "max_episode_steps": 10000}
    rpc = MetaEnvRpc({**expected, "original90_grasp_diagnostic_v1": True})
    client = V5SkillEnvClient(rpc, expected_meta=expected)
    assert client.last_obs == {"step": 0}
    assert expected == {"suite": "libero_90", "task": 7, "seed": 13, "max_episode_steps": 10000}


@pytest.mark.parametrize("difference", [
    {"task": 8}, {"seed": 14}, {"max_episode_steps": 9999},
    {"original90_grasp_diagnostic_v1": False}, {"unregistered_flag": True},
])
def test_original90_diagnostic_still_strictly_matches_every_metadata_field(difference):
    expected = {"suite": "libero_90", "task": 7, "seed": 13, "max_episode_steps": 10000}
    rpc = MetaEnvRpc({**expected, "original90_grasp_diagnostic_v1": True, **difference})
    with pytest.raises(AssertionError, match="env_meta mismatch"):
        V5SkillEnvClient(rpc, expected_meta=expected)


def test_original90_explicit_false_is_not_silently_overridden():
    expected = {"suite": "libero_90", "task": 7, "seed": 13, "max_episode_steps": 10000,
                "original90_grasp_diagnostic_v1": False}
    rpc = MetaEnvRpc({**expected, "original90_grasp_diagnostic_v1": True})
    with pytest.raises(AssertionError, match="env_meta mismatch"):
        V5SkillEnvClient(rpc, expected_meta=expected)


def test_standard_original_suite_does_not_silently_accept_diagnostic_flag():
    expected = {"suite": "libero_spatial", "task": 0, "seed": 0, "max_episode_steps": 10000}
    rpc = MetaEnvRpc({**expected, "original90_grasp_diagnostic_v1": True})
    with pytest.raises(AssertionError, match="env_meta mismatch"):
        V5SkillEnvClient(rpc, expected_meta=expected)
