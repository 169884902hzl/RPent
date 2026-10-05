"""Original endpoint diagnostics label transitions without truth-based routing."""

from types import SimpleNamespace

import pytest

from scripts import probe_v5_fixture526_original as probe


class RPC:
    def __init__(self, requested):
        self.requested = iter(requested)
        self.calls = []

    def call(self, method, kwargs=None, **_):
        self.calls.append((method, kwargs))
        if method == "oracle.skill501_truth":
            return {"satisfied": next(self.requested)}
        return {"executed_controls": 5}


def test_already_satisfied_is_preserved_but_not_newly_achieved():
    assert probe.endpoint_transition(True, True) == "already_satisfied_preserved"
    assert probe.endpoint_transition(True, False) == "already_satisfied_destroyed"
    assert probe.endpoint_transition(False, True) == "new_requested_endpoint"


def test_registered_prompt_restores_even_after_contact_exception():
    calls = []

    def vla_act(text, max_chunks, stop, *args, **kwargs):
        calls.append(text)
        raise RuntimeError("physical development failure")

    executor = SimpleNamespace(vla_act=vla_act)
    with pytest.raises(RuntimeError, match="physical development failure"):
        with probe.registered_prompt(executor, "open the microwave"):
            executor.vla_act("harness prompt", 160, "endpoint")
    assert calls == ["open the microwave"]
    assert executor.vla_act is vla_act


@pytest.mark.parametrize("labels", [[True, False, True, False], [False, True, True, False]])
def test_labels_do_not_route_or_skip_the_same_physical_first_action(monkeypatch, labels):
    actions = []
    rpc = RPC(labels)
    executor = SimpleNamespace(vla_act=lambda *_: {})

    def stage(executor, policy, rpc, spec, tool, phase, **kwargs):
        actions.append((tool, phase))
        return {"phase": phase, "receipt": {}}

    def run_case(case, condition, base, endpoints, output):
        return {"setup": [], "first_attempt": probe.base_probe.execute_stage(
            executor, None, rpc, case, "articulate", "first_attempt")}

    monkeypatch.setattr(probe.base_probe, "execute_stage", stage)
    monkeypatch.setattr(probe.base_probe, "run_case", run_case)
    original_module = probe.base_probe.PROBE_MODULE
    case = {"mode": "open", "object_symbol": "microwave_1"}
    with probe.diagnostic_hooks():
        result = probe.base_probe.run_case(case, {"executor": "current", "max_chunks": 160}, {}, {}, None)
        assert probe.base_probe.PROBE_MODULE == "robots.libero.v5_fixture_probe_env"
    assert probe.base_probe.execute_stage is stage
    assert probe.base_probe.run_case is run_case
    assert probe.base_probe.PROBE_MODULE == original_module
    assert actions == [("articulate", "first_attempt")]
    assert result["newly_achieved_requested_endpoint"] is (labels[0] is False)
    assert result["first_attempt"]["private_labels_used_for_control"] is False
    assert [m for m, _ in rpc.calls].count("diagnostic.fixture_chunk_start") == 1
    assert [m for m, _ in rpc.calls].count("diagnostic.fixture_chunk_end") == 1
