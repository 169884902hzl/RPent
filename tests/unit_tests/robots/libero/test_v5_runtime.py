# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Composite skills must publish the native task result before evaluation."""

from types import SimpleNamespace

from robots.libero import tools
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_runtime import V5Executor, segmentation_prompt


def test_composite_capture_updates_the_real_toolkit_completion_cache(monkeypatch):
    toolkit = LiberoToolkit.__new__(LiberoToolkit)
    toolkit._primitives = SimpleNamespace(recorded_frame_count=lambda: 1)
    toolkit._state = object()
    toolkit._solved = False
    toolkit._action_frame_cursor = 0
    toolkit._dashboard_events = SimpleNamespace(enabled=False)
    monkeypatch.setattr(
        tools,
        "dump_state",
        lambda *a, **kw: SimpleNamespace(terminated=True, step_idx=1),
    )
    monkeypatch.setattr(tools, "view_env_state", lambda *a, **kw: {})
    assert not toolkit.solved()
    V5Executor(toolkit, SimpleNamespace()).capture()
    assert toolkit.solved()


def test_package_aliases_do_not_conflate_the_two_original_cans():
    assert segmentation_prompt("alphabet soup") == "blue can"
    assert segmentation_prompt("tomato sauce") == "red and green can"


def test_articulation_preserves_the_public_middle_drawer_reference():
    from robots.libero.v5_state import Candidate, Entity

    cabinet = Entity("e9", "cabinet", (0, 0, 1), (0, 0, 0.9), (0.2, 0.2, 1.2))
    executor = V5Executor(
        SimpleNamespace(primitives=None),
        SimpleNamespace(entities={"e9": cabinet}),
        instruction="open the middle drawer of the cabinet",
    )
    prompts = []
    executor.vla_act = lambda prompt, *a: prompts.append(prompt) or {"executed": True}
    executor._refresh = lambda names: None
    receipt = {}
    executor._execute(Candidate("articulate", "e9", mode="open"), receipt, None)
    assert prompts == ["open the middle drawer of the cabinet"]
    assert receipt["verification"] == "unverified"


def test_place_clears_the_measured_rim_and_reuses_grasp_offset():
    import numpy as np

    from robots.libero.v5_state import Candidate, Entity

    obj = Entity(
        "e1", "alphabet soup", (0, 0, 0.15), (-0.03, -0.03, 0.11), (0.03, 0.03, 0.19)
    )
    basket = Entity(
        "e2", "basket", (0.1, 0.25, 0.1), (0.02, 0.17, 0.04), (0.18, 0.33, 0.18)
    )
    p = SimpleNamespace(
        _last_obs_eef_pos=np.array([0.07, 0.24, 0.14]),
        env=SimpleNamespace(terminated=False, truncated=False),
    )
    scene = SimpleNamespace(entities={"e1": obj, "e2": basket})
    executor = V5Executor(SimpleNamespace(primitives=p), scene)
    executor.held = "e1"
    executor.held_offset = np.array([0, 0, 0.01])
    waypoints = []

    def move(xyz, gripper):
        waypoints.append(np.asarray(xyz).copy())
        if len(waypoints) == 3:
            raise RuntimeError("stop after waypoint probe")

    executor.move = move
    try:
        executor._execute(Candidate("place", "e1", "e2", "in"), {}, None)
    except RuntimeError:
        pass
    np.testing.assert_allclose(waypoints[0][:2], p._last_obs_eef_pos[:2])
    assert waypoints[1][2] >= basket.upper[2] + 0.04 + 0.01 + 0.1
    np.testing.assert_allclose(waypoints[1][:2], basket.xyz[:2])


def test_v5_chunk_stops_before_actions_after_native_termination():
    import numpy as np

    from robots.libero.v5_env_server import V5EnvFacade

    facade = V5EnvFacade.__new__(V5EnvFacade)
    calls = []

    def step(action):
        calls.append(action)
        return {"step": len(calls)}, 1.0, len(calls) == 2, False, {}

    facade.step = step
    obs, rewards, term, trunc, _ = facade.chunk_step(
        np.zeros((50, 7)), return_all_frames=True
    )
    assert len(calls) == len(obs) == len(rewards) == 2
    assert term.tolist() == [False, True]
    assert not trunc.any()
