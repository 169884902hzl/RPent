"""Original native success must not truncate a reverse fixture skill probe."""

from types import MethodType

import numpy as np
import pytest

from robots.libero.v5_fixture_probe_env import FixtureProbeFacade


def facade(*, truncate_at=None):
    obj = FixtureProbeFacade.__new__(FixtureProbeFacade)
    obj._fixture_chunk_scope = None
    obj._fixture_phases = []
    obj.calls = 0

    def step(self, action):
        self.calls += 1
        return ({"sequence": self.calls}, 1., np.array(True),
                np.array(self.calls == truncate_at), {"native_goal": "true"})

    obj.step = MethodType(step, obj)
    return obj


@pytest.mark.parametrize("has_setup", [True, False])
def test_fixed_scope_keeps_native_success_and_all_controls(has_setup):
    obj = facade()
    if has_setup:
        obj.fixture_chunk_start("setup", 160)
        obj.chunk_step(np.zeros((5, 7)))
        assert obj.fixture_chunk_end()["executed_controls"] == 5
    obj.fixture_chunk_start("first_attempt", 160)
    before = obj.calls
    obs, _, term, trunc, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert [o["sequence"] for o in obs] == list(range(before + 1, before + 6))
    assert term.tolist() == [True] * 5
    assert trunc.tolist() == [False] * 5
    summary = obj.fixture_chunk_end()
    assert summary["executed_controls"] == summary["requested_controls"] == 5
    assert summary["raw_native_success_controls"] == 5


def test_unscoped_diagnostic_uses_normal_native_stop_rule():
    obj = facade()
    obs, _, term, _, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert obj.calls == len(obs) == len(term) == 1


def test_external_truncation_is_immediate_and_preserved():
    obj = facade(truncate_at=3)
    obj.fixture_chunk_start("first_attempt", 160)
    obs, _, _, trunc, _ = obj.chunk_step(np.ones((5, 7)), return_all_frames=True)
    assert len(obs) == 3
    assert trunc.tolist() == [False, False, True]
    with pytest.raises(RuntimeError, match="after external truncation"):
        obj.chunk_step(np.ones((5, 7)))
    assert obj.fixture_chunk_end()["external_truncation"] is True


def test_scope_order_and_finite_budget_cannot_be_changed():
    obj = facade()
    with pytest.raises(ValueError, match="order or budget"):
        obj.fixture_chunk_start("first_attempt", 161)
    obj.fixture_chunk_start("first_attempt", 160)
    with pytest.raises(ValueError, match="length/budget"):
        obj.chunk_step(np.ones((6, 7)))
    for _ in range(160):
        obj.chunk_step(np.ones((5, 7)))
    with pytest.raises(ValueError, match="length/budget"):
        obj.chunk_step(np.ones((5, 7)))
    assert obj.fixture_chunk_end()["executed_controls"] == 800
    with pytest.raises(ValueError, match="order or budget"):
        obj.fixture_chunk_start("setup", 160)
    with pytest.raises(ValueError, match="order or budget"):
        obj.fixture_chunk_start("first_attempt", 160)
