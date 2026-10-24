# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Physical public depth, rather than ID or mask jitter, unlocks failures."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_failure_history import confirmed_changes
from rpent.skill_package.contract import FailureMemory


@pytest.mark.parametrize('physical_steps', [0, 1])
@pytest.mark.parametrize('displacement', [(0., 0., 0.), (.02, 0., 0.), (.015, .015, 0.)])
def test_depth_motion_required_despite_shifted_mask_centre(physical_steps, displacement):
    rng = np.random.default_rng(509)
    old = rng.uniform(-.02, .02, (900, 3))
    shift = np.asarray(displacement)
    delta = shift if shift.any() else np.array([.012, 0., 0.])
    memory = FailureMemory()
    candidate = {'skill': 'move_to', 'parameters': {'anchor_id': 'e1'}}
    for _ in range(2):
        memory.record(candidate, 'failure', 'measured_sweep_collision')
    adapter = SimpleNamespace(memory=memory, previous_scene={'e1': np.zeros(3)},
        p=SimpleNamespace(env=SimpleNamespace(execution_budget=lambda: {'used_sim_steps': physical_steps})),
        _failure_scene_sim_steps=0, registration_query_workers=1,
        scene=SimpleNamespace(entities={'e1': SimpleNamespace(xyz=delta)},
                              measurement_clouds={'e1': old+shift}))
    changed, evidence = confirmed_changes(adapter, {'e1'}, {'e1': old})
    assert (changed == {'e1'}) == bool(physical_steps and shift.any())
    memory.tick(scene_changed=bool(changed), changed_anchors=changed)
    assert bool(memory.apply([candidate])) == bool(physical_steps and shift.any())
    assert evidence['private_truth_used'] is False


def test_new_anchor_id_and_missing_depth_cannot_unlock_retries():
    memory = FailureMemory()
    memory.record({'skill': 'move_to', 'parameters': {'anchor_id': 'old'}}, 'failure', 'numerical_ik_not_found')
    adapter = SimpleNamespace(memory=memory, previous_scene={'old': np.zeros(3)},
        p=SimpleNamespace(env=SimpleNamespace(execution_budget=lambda: {'used_sim_steps': 1})),
        _failure_scene_sim_steps=0, registration_query_workers=1,
        scene=SimpleNamespace(entities={'new': SimpleNamespace(xyz=[.2, 0., 0.])}, measurement_clouds={}))
    assert confirmed_changes(adapter, {'new'}, {})[0] == set()
