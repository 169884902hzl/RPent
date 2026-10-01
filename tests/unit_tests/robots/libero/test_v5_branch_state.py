"""A branch restores accumulated hand commands in addition to joint positions."""

from types import SimpleNamespace

import numpy as np

from robots.libero.v5_branch_state import actuator_state, restore_actuators


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
