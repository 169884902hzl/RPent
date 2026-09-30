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
