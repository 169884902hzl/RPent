"""Capture the mutable actuator state omitted by MuJoCo's flat qpos snapshot."""

from __future__ import annotations

import copy
import types

import numpy as np

DATA_FIELDS = ("ctrl", "qacc_warmstart", "mocap_pos", "mocap_quat", "userdata", "qfrc_applied", "xfrc_applied")
CONTROLLER_FIELDS = ("goal_pos", "goal_ori", "goal_qpos", "goal_qvel", "_goal_update_mode", "ori_ref", "relative_ori")


def actuator_state(wrapper):
    """Return private controller and integrated gripper commands, without stepping."""
    env = wrapper.env
    robots = []
    for robot in env.robots:
        grippers = robot.gripper if isinstance(robot.gripper, dict) else {"gripper": robot.gripper}
        controllers = getattr(robot, "part_controllers", None)
        if controllers is None:
            controllers = {"controller": robot.controller}
        controls = {}
        for name, controller in controllers.items():
            if any(getattr(controller, field, None) is not None for field in ("interpolator_pos", "interpolator_ori", "interpolator")):
                raise ValueError("branch snapshot has no interpolator contract for this controller")
            controls[name] = {field: copy.deepcopy(getattr(controller, field))
                              for field in CONTROLLER_FIELDS if hasattr(controller, field)}
        robots.append({"grippers": {name: {"type": type(gripper).__name__, "current_action": copy.deepcopy(gripper.current_action)}
                                     for name, gripper in grippers.items()}, "controllers": controls})
    return {"data": {field: np.array(getattr(env.sim.data, field), copy=True)
                     for field in DATA_FIELDS if hasattr(env.sim.data, field)}, "robots": robots}


def restore_actuators(wrapper, saved):
    """Restore commands along with qpos; a branch must not leave the hand opening."""
    env = wrapper.env
    if len(env.robots) != len(saved["robots"]):
        raise ValueError("robot identity changed during branch")
    for robot, state in zip(env.robots, saved["robots"]):
        grippers = robot.gripper if isinstance(robot.gripper, dict) else {"gripper": robot.gripper}
        for name, item in state["grippers"].items():
            gripper = grippers[name]
            if type(gripper).__name__ != item["type"]:
                raise ValueError("gripper identity changed during branch")
            gripper.current_action = copy.deepcopy(item["current_action"])
        controllers = getattr(robot, "part_controllers", None)
        if controllers is None:
            controllers = {"controller": robot.controller}
        for name, fields in state["controllers"].items():
            controller = controllers[name]
            controller.update(force=True)
            for field, value in fields.items():
                setattr(controller, field, copy.deepcopy(value))
    for field, value in saved["data"].items():
        getattr(env.sim.data, field)[:] = value
    env.sim.forward()
    wrapper._update_observables(force=True)
    return env._get_observations()


def attach_branch_state(wrapper):
    """Attach two private methods inside RLinf's existing worker factory."""
    wrapper.v5_actuator_state = types.MethodType(actuator_state, wrapper)
    wrapper.v5_restore_actuators = types.MethodType(restore_actuators, wrapper)
    return wrapper
