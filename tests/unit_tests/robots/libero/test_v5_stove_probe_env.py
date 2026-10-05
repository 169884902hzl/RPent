"""A solved turnon task must not reduce a fixed turnoff diagnostic chunk."""

from types import MethodType

import numpy as np
import pytest

from robots.libero.v5_stove_probe_env import StoveProbeFacade


def facade(*, truncate_at=None):
    obj = StoveProbeFacade.__new__(StoveProbeFacade)
    obj._stove_chunk_scope = None
    obj._next_stove_phase = "on"
    obj.calls = 0

    def step(self, action):
        self.calls += 1
        # The original turnon goal is already true. All five input actions
        # must physically run inside the fixed independent contact scope.
        return ({"sequence": self.calls}, float(self.calls), np.array(True),
                np.array(self.calls == truncate_at), {"native_goal": "on"})

    obj.step = MethodType(step, obj)
    return obj


def test_native_success_preserved_and_all_five_actions_execute_inside_scope():
    obj = facade()
    obj.stove_chunk_start("on", 160)
    obs, _, term, trunc, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert [o["sequence"] for o in obs] == list(range(1, 6))
    assert term.tolist() == [True] * 5
    assert trunc.tolist() == [False] * 5
    summary = obj.stove_chunk_end()
    assert summary["executed_controls"] == summary["requested_controls"] == 5
    assert summary["raw_native_success_controls"] == 5
    obj.stove_chunk_start("off", 160)
    obj.chunk_step(np.ones((5, 7)))
    assert obj.stove_chunk_end()["executed_controls"] == 5


def test_unscoped_default_keeps_shared_native_stop_rule():
    obj = facade()
    obs, _, term, _, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert obj.calls == 1
    assert len(obs) == len(term) == 1


def test_external_truncation_stops_scope_immediately_and_is_preserved():
    obj = facade(truncate_at=3)
    obj.stove_chunk_start("on", 160)
    obs, _, _, trunc, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert len(obs) == 3
    assert trunc.tolist() == [False, False, True]
    with pytest.raises(RuntimeError, match="after external truncation"):
        obj.chunk_step(np.ones((5, 7)))
    assert obj.stove_chunk_end()["external_truncation"] is True


def test_scope_order_budget_and_action_count_are_registered():
    obj = facade()
    with pytest.raises(ValueError, match="order or chunk budget"):
        obj.stove_chunk_start("off", 160)
    with pytest.raises(ValueError, match="order or chunk budget"):
        obj.stove_chunk_start("on", 161)
    obj.stove_chunk_start("on", 160)
    with pytest.raises(ValueError, match="chunk length/budget exceeded"):
        obj.chunk_step(np.ones((6, 7)))
    for _ in range(160):
        obj.chunk_step(np.ones((5, 7)))
    assert obj.calls == 800
    with pytest.raises(ValueError, match="chunk length/budget exceeded"):
        obj.chunk_step(np.ones((5, 7)))
    assert obj.stove_chunk_end()["executed_controls"] == 800
