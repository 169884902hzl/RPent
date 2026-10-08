"""A stove unload moves while opening and cannot manufacture verification."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def make_executor(**kwargs):
    stove = Entity("e1", "stove", (0., 0., .92), (-.1, -.1, .90), (.1, .1, .94))
    env = SimpleNamespace(terminated=False, truncated=False)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.03, env=env)
    actions = []

    def step(action):
        actions.append(action.copy())
        p._last_obs_eef_pos += action[:3] * .01
        p._last_obs_gripper = .08

    p._step_env = step
    scene = SimpleNamespace(entities={stove.id: stove}, fixture_handle_geometry_v3=False,
                            fixture_front_geometry_v1=False,
                            view_axes=((1., 0., 0.), (0., 1., 0.)))
    ex = V5Executor(SimpleNamespace(primitives=p), scene, **kwargs)
    ex._refresh = lambda names: None
    ex.measure_stove = lambda parent: {"state": "on", "entity": parent.id, "source_step": 1}
    ex.verify_stove = lambda *args: (None, {"reason": "strict_off_not_measured"})
    ex.vla_act = lambda *args, **kw: {"executed": True, "chunks": 20}
    return ex, stove, actions


@pytest.mark.parametrize("tool", ["articulate", "vla_subtask"])
def test_both_stove_skills_use_simultaneous_unload_without_claiming_verified(tool):
    ex, stove, actions = make_executor(stove_contact_unload_v1=True, articulate_view_retreat_v1=True)
    ex.retreat = lambda: pytest.fail("standalone release/retreat must not follow simultaneous unload")
    receipt = {}
    ex._execute(Candidate(tool, stove.id, mode="turn_off"), receipt, None)
    assert len(actions) == 60
    assert all(action[2] > 0 and action[-1] == -1 for action in actions[:20])
    assert all(np.all(action[:6] == 0) and action[-1] == -1 for action in actions[20:])
    assert receipt["post_contact_recovery"]["executed_controls"] == 60
    assert receipt["articulate_verified"] is None
    assert receipt["verification"] == "unmeasured"


@pytest.mark.parametrize("tool", ["articulate", "vla_subtask"])
def test_default_stove_execution_does_not_unload(tool):
    ex, stove, actions = make_executor()
    ex._execute(Candidate(tool, stove.id, mode="turn_off"), {}, None)
    assert not actions


def test_native_termination_stops_unload_and_accounts_only_actual_controls():
    ex, _, actions = make_executor(stove_contact_unload_v1=True)
    original = ex.p._step_env

    def terminate(action):
        original(action)
        ex.p.env.terminated = True

    ex.p._step_env = terminate
    evidence = ex.clear_stove_contact()
    assert len(actions) == evidence["executed_controls"] == 1
    assert evidence["phases"][0]["executed_controls"] == 1
    assert evidence["phases"][1]["executed_controls"] == 0
    assert evidence["endpoint_verified"] is None
