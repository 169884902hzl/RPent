# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""D2-only admission, unchanged rules and branch state isolation."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_hybrid_diagnostic import (
    D2_SUITES,
    capture_runtime,
    choose_branch,
    restore_runtime,
    snapshot_digest,
    split_subtasks,
    validate_d2_episode,
)


def test_d2_admission_is_exactly_the_registered_forty():
    for suite in D2_SUITES:
        for task in range(5):
            validate_d2_episode({"suite": suite, "task": task, "seed": 40})
    for update in ({"task": 5}, {"seed": 41}, {"suite": "libero_spatial"},
                   {"suite": "libero_goal_swap", "task": True}, {"extra": "test"}):
        with pytest.raises(ValueError):
            validate_d2_episode({"suite": "libero_spatial_swap", "task": 0, "seed": 40} | update)


def test_split_only_uses_existing_modes_and_reports_uncovered_rules():
    tasks, unsupported = split_subtasks([
        ["on", "bowl_1", "plate_1"], ["open", "cabinet_1"],
        ["turnoff", "stove_1"], ["touch", "cup_1"],
        ["and", ["open", "drawer_1"], ["close", "drawer_2"]],
    ])
    assert [t["mode"] for t in tasks] == ["pick", "on", "open", "turn_off"]
    assert [t["id"] for t in tasks] == ["g0:pick", "g0:on", "g1:open", "g2:turn_off"]
    assert [t["index"] for t in unsupported] == [3, 4]


def test_unknown_is_not_failure_and_tie_prefers_self():
    assert choose_branch(True, [True, True, True])["method"] == "self"
    assert choose_branch(False, [False, True, False])["rate"] == 1 / 3
    assert choose_branch(False, [False, False, False])["status"] == "both_failed"
    assert choose_branch(False, [False, None, False])["method"] is None
    with pytest.raises(ValueError):
        choose_branch(False, [True])


def test_runtime_restore_does_not_leak_sibling_caches_or_retry_history():
    p = SimpleNamespace(_bounded_control_index=10, client=object())
    scene = SimpleNamespace(toolkit=object(), rpc=object(), entities={"e1": [1]}, calls=1)
    adapter = SimpleNamespace(ex=object(), p=p, scene=scene, receipts=[{"outcome": "failure"}],
                              held=None, memory={"tries": 1})
    policy = SimpleNamespace(binding=SimpleNamespace(rpc=object(), _bindings={"bowl": "e1"}),
                             private_trace=[{"goal": "g0"}])
    state = capture_runtime(adapter, policy)
    resource_ids = (id(scene.toolkit), id(adapter.ex), id(policy.binding.rpc))
    scene.entities["e1"].append(2)
    adapter.memory["tries"] = 99
    p._bounded_new_trace = [42]
    p._bounded_control_index = 40
    policy.binding._bindings["bowl"] = "wrong"
    restore_runtime(adapter, policy, state)
    assert (id(scene.toolkit), id(adapter.ex), id(policy.binding.rpc)) == resource_ids
    assert scene.entities == {"e1": [1]} and adapter.memory == {"tries": 1}
    assert p._bounded_control_index == 10 and not hasattr(p, "_bounded_new_trace")
    adapter.memory["tries"] = 2
    restore_runtime(adapter, policy, state)
    assert adapter.memory["tries"] == 1


def test_physical_identity_includes_controller_and_counter_state():
    first = {"sim_state": np.array([1., 2.]), "controller": {"goal_pos": [3., 4.]}, "counter": 10}
    assert snapshot_digest(first) == snapshot_digest(dict(reversed(list(first.items()))))
    assert snapshot_digest(first) != snapshot_digest(first | {"counter": 11})
