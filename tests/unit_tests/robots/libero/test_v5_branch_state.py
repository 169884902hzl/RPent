# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""A branch restores accumulated hand commands in addition to joint positions."""

from types import SimpleNamespace

import numpy as np

from robots.libero.v5_branch_state import (
    actuator_state,
    attach_branch_state,
    restore_actuators,
)


def test_branch_open_does_not_change_the_original_holding_command():
    controller = SimpleNamespace(goal_pos=np.array([1., 2., 3.]), goal_ori=np.eye(3), update=lambda **kwargs: None)
    gripper = SimpleNamespace(current_action=np.array([1., 1.]))
    data = SimpleNamespace(ctrl=np.array([.5, .8]), qacc_warmstart=np.array([.3, .1]))
    env = SimpleNamespace(robots=[SimpleNamespace(gripper=gripper, part_controllers={"right": controller})],
                          sim=SimpleNamespace(data=data, forward=lambda: None), _get_observations=lambda: {})
    wrapper = SimpleNamespace(env=env, _update_observables=lambda **kwargs: None)
    snapshot = actuator_state(wrapper)
    gripper.current_action[:] = -1
    controller.goal_pos[:] = 20
    data.ctrl[:] = -5
    restore_actuators(wrapper, snapshot)
    np.testing.assert_array_equal(gripper.current_action, [1., 1.])
    np.testing.assert_array_equal(controller.goal_pos, [1., 2., 3.])
    np.testing.assert_array_equal(data.ctrl, [.5, .8])


def test_storage_open_uses_parent_only_for_jointless_interior_regions():
    states = {
        "microwave_heating": SimpleNamespace(object_state_type="site", parent_name="microwave"),
        "cabinet_bottom": SimpleNamespace(object_state_type="site", parent_name="cabinet"),
        "microwave": SimpleNamespace(object_state_type="object"),
    }
    sites = {"microwave_heating": SimpleNamespace(joints=[]),
             "cabinet_bottom": SimpleNamespace(joints=["bottom_joint"])}
    predicates = {"microwave_heating": False, "microwave": True,
                  "cabinet_bottom": False, "cabinet": True}
    queried = []

    def evaluate(predicate):
        queried.append(predicate)
        return predicates[predicate[1]]

    wrapper = attach_branch_state(SimpleNamespace(env=SimpleNamespace(
        object_states_dict=states, object_sites_dict=sites, _eval_predicate=evaluate)))
    assert wrapper.v5_storage_open("microwave_heating") is True
    assert wrapper.v5_storage_open("cabinet_bottom") is False
    assert wrapper.v5_storage_open("microwave") is True
    assert queried == [["open", "microwave"], ["open", "cabinet_bottom"], ["open", "microwave"]]
