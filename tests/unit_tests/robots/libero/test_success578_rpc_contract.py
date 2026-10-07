"""The passive hook must call the real RPC interface before a physical action."""

import inspect
from types import SimpleNamespace

import pytest

from robots.libero.v5_state import Candidate
from rpent.utils.rpc.http_rpc import HttpRpcClient
from scripts import run_original_success578 as probe


@pytest.mark.parametrize("physical_error", [False, True])
def test_passive_hook_uses_actual_rpc_signature_and_closes_label_window(monkeypatch, physical_error):
    monkeypatch.setattr(probe, "ACTIVE", None)
    calls, physical = [], []
    signature = inspect.signature(HttpRpcClient.call)
    class Client:
        def call(self, *args, **kwargs):
            # Bind against the real installed API. Arbitrary **kwargs on a
            # mock previously hid the job4498 unexpected-sequence failure.
            signature.bind(self, *args, **kwargs)
            calls.append((args, kwargs))
            return {"logged": True}
    executor = SimpleNamespace(scene=SimpleNamespace(entities={}),
                               p=SimpleNamespace(env=SimpleNamespace(_client=Client())))
    action = Candidate("release")
    def execute(*args):
        physical.append(args[1])
        if physical_error:
            raise RuntimeError("physical action error")
        return {"executed": True}, args[1]
    run = probe.instrument_execute(execute)
    if physical_error:
        with pytest.raises(RuntimeError, match="physical action error"):
            run(executor, action, None, None, {})
    else:
        assert run(executor, action, None, None, {}) == ({"executed": True}, action)
    assert physical == [action]
    assert [args[0] for args, _ in calls] == ["diagnostic.action_begin", "diagnostic.action_end"]
    assert calls[0][1]["kwargs"]["sequence"] == 0
    assert calls[0][1]["kwargs"]["source"] is None
    assert calls[0][1]["timeout_s"] == calls[1][1]["timeout_s"] == 120
