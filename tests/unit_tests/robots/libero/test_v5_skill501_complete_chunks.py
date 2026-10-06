"""A latched original goal cannot shorten an independent skill diagnostic."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_env_server import V5EnvFacade
from scripts.probe_v5_skill501_original import complete_probe_chunk


def facade(*, truncate_at=None):
    calls = []

    def step(action):
        calls.append(action.copy())
        return {"control": len(calls)}, 1., True, len(calls) == truncate_at, {}

    return SimpleNamespace(step=step, calls=calls, _skill_chunk_accounting={
        "chunks_requested": 0, "requested_controls": 0,
        "executed_controls": 0, "raw_native_success_controls": 0,
        "external_truncation": False,
    })


def test_owned_skill_keeps_all_controls_and_raw_native_flags():
    obj = facade()
    actions = np.arange(35).reshape(5, 7)
    for _ in range(2):
        obs, _, term, trunc, _ = complete_probe_chunk(obj, actions, return_all_frames=True)
        assert len(obs) == 5
        assert term.tolist() == [True] * 5
        assert not trunc.any()
    np.testing.assert_array_equal(np.stack(obj.calls), np.tile(actions, (2, 1)))
    assert obj._skill_chunk_accounting == {
        "chunks_requested": 2, "requested_controls": 10,
        "executed_controls": 10, "raw_native_success_controls": 10,
        "external_truncation": False,
    }


def test_external_budget_stops_inside_chunk_and_forbids_further_actions():
    obj = facade(truncate_at=3)
    obs, _, term, trunc, _ = complete_probe_chunk(obj, np.zeros((5, 7)), return_all_frames=True)
    assert len(obs) == 3 and term.all()
    assert trunc.tolist() == [False, False, True]
    assert obj._skill_chunk_accounting["executed_controls"] == 3
    with pytest.raises(RuntimeError, match="external truncation"):
        complete_probe_chunk(obj, np.zeros((5, 7)))
    assert len(obj.calls) == 3


def test_diagnostic_does_not_change_rollout_native_stop_rule():
    obj = facade()
    obs, _, term, _, _ = V5EnvFacade.chunk_step(obj, np.zeros((5, 7)), return_all_frames=True)
    assert len(obj.calls) == len(obs) == len(term) == 1
    assert obj._skill_chunk_accounting["executed_controls"] == 0


@pytest.mark.parametrize("shape", [(0, 7), (6, 7), (7,)])
def test_unregistered_chunk_length_is_rejected_without_motion(shape):
    obj = facade()
    with pytest.raises(ValueError, match="five-action chunks"):
        complete_probe_chunk(obj, np.zeros(shape))
    assert not obj.calls
