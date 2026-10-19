# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Capture actuator and fixture state omitted by MuJoCo's flat snapshot."""

from __future__ import annotations

import copy
import random
import types

import numpy as np

DATA_FIELDS = ("ctrl", "qacc_warmstart", "mocap_pos", "mocap_quat", "userdata", "qfrc_applied", "xfrc_applied")
CONTROLLER_FIELDS = ("goal_pos", "goal_ori", "goal_qpos", "goal_qvel", "_goal_update_mode", "ori_ref", "relative_ori")
OBSERVABLE_FIELDS = ("_sampling_timestep", "_enabled", "_active", "_time_since_last_sample",
                     "_current_delay", "_current_observed_value", "_sampled")


def observation_state(env):
    """Private public-sensor scheduling/buffers, separate from physical qpos."""
    return {'version': 'robosuite-observation-branch/1',
        'clock': {name: copy.deepcopy(getattr(env, name)) for name in ('timestep', 'cur_time') if hasattr(env, name)},
        'cache': copy.deepcopy(getattr(env, '_obs_cache', {})),
        'observables': {name: {field: copy.deepcopy(getattr(observable, field))
            for field in OBSERVABLE_FIELDS if hasattr(observable, field)}
            for name, observable in getattr(env, '_observables', {}).items()}}


def restore_observation_state(wrapper, saved):
    """Restore buffered public sensors without incrementing their sample clock."""
    env = wrapper.env
    observables = getattr(env, '_observables', {})
    if saved is None:
        # Historical snapshots omitted this state. Canonical fresh sampling
        # cannot recover their unknown phase, but must not inherit a sibling's.
        if hasattr(env, 'cur_time'):
            env.cur_time = float(env.sim.data.time)
        if hasattr(env, 'timestep'):
            env.timestep = int(round(float(env.sim.data.time)/env.control_timestep))
        if hasattr(env, '_obs_cache'):
            env._obs_cache.clear()
        for observable in observables.values():
            observable.reset()
            observable._sampled = False
        wrapper._update_observables(force=True)
    else:
        if saved['version'] != 'robosuite-observation-branch/1' or set(observables) != set(saved['observables']):
            raise ValueError('observable identity changed during branch')
        for name, value in saved['clock'].items():
            setattr(env, name, copy.deepcopy(value))
        for name, fields in saved['observables'].items():
            for field, value in fields.items():
                setattr(observables[name], field, copy.deepcopy(value))
        env._obs_cache = copy.deepcopy(saved['cache'])
    return env._get_observations()


def _rng_nodes(env):
    result = {"env": env}
    def visit(path, sampler):
        if sampler is not None:
            result[path] = sampler
            for name, child in getattr(sampler, "samplers", {}).items():
                visit(path+"/"+name, child)
    for name in ("placement_initializer", "conditional_placement_initializer", "conditional_placement_on_objects_initializer"):
        visit(name, getattr(env, name, None))
    return result


def rng_state(env):
    """Private branch state, including legacy and generator-based samplers."""
    generators = {}
    for path, node in _rng_nodes(env).items():
        rng = getattr(node, "rng", None)
        if isinstance(rng, np.random.Generator):
            generators[path] = {"kind": "Generator", "state": copy.deepcopy(rng.bit_generator.state)}
        elif isinstance(rng, np.random.RandomState):
            generators[path] = {"kind": "RandomState", "state": copy.deepcopy(rng.get_state())}
    return {"python": random.getstate(), "numpy": np.random.get_state(), "generators": generators}


def restore_rng(env, saved):
    def tuples(value):
        return tuple(tuples(item) for item in value) if isinstance(value, (list, tuple)) else value
    random.setstate(tuples(saved["python"]))
    np.random.set_state(saved["numpy"])
    nodes = _rng_nodes(env)
    for path, record in saved["generators"].items():
        rng = nodes[path].rng
        if record["kind"] == "Generator" and isinstance(rng, np.random.Generator):
            rng.bit_generator.state = copy.deepcopy(record["state"])
        elif record["kind"] == "RandomState" and isinstance(rng, np.random.RandomState):
            rng.set_state(record["state"])
        else:
            raise ValueError("branch RNG type changed: "+path)


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
    return {"model": {field: np.array(getattr(env.sim.model, field), copy=True)
                      for field in ("body_pos", "body_quat")},
            "data": {field: np.array(getattr(env.sim.data, field), copy=True)
                     for field in DATA_FIELDS if hasattr(env.sim.data, field)}, "robots": robots,
            "rng": rng_state(env), "observation_state": observation_state(env)}


def restore_actuators(wrapper, saved):
    """Restore commands along with qpos; a branch must not leave the hand opening."""
    env = wrapper.env
    if len(env.robots) != len(saved["robots"]):
        raise ValueError("robot identity changed during branch")
    # LIBERO resets fixed furniture through model body transforms, outside
    # qpos. Recreating the same robot state does not recreate that furniture.
    # Restore it before controllers/observations query forward kinematics.
    for field, value in saved.get("model", {}).items():
        current = getattr(env.sim.model, field)
        if current.shape != np.asarray(value).shape:
            raise ValueError("branch model shape changed: "+field)
        current[:] = value
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
    observations = restore_observation_state(wrapper, saved.get('observation_state'))
    # forward() rebuilds solver input. Keep its captured integration warmstart
    # after observations, as required by the strict complete-state identity.
    if 'qacc_warmstart' in saved['data']:
        env.sim.data.qacc_warmstart[:] = saved['data']['qacc_warmstart']
    if "rng" in saved:
        restore_rng(env, saved["rng"])
    return observations


def storage_open(wrapper, region):
    """Query a movable region's joints, or its fixture for a fixed interior.

    LIBERO's microwave heating region has no joints, so its own Open predicate
    is always false. Drawer regions do have joints and must remain region
    specific: another open drawer does not make the requested drawer open.
    """
    env = wrapper.env
    state = env.object_states_dict[region]
    if state.object_state_type == "site" and not env.object_sites_dict[region].joints:
        region = state.parent_name
    return bool(env._eval_predicate(["open", region]))


def reference_geometry(wrapper):
    """Return original-task body origins for private localization diagnostics."""
    env = wrapper.env
    return {name: {"xyz": np.asarray(env.sim.data.body_xpos[index]).tolist(),
                   "reference": "body_origin", "source": "simulation_diagnostic_only"}
            for name, index in env.obj_body_id.items()}


def grasp_contacts(wrapper):
    """Read dual-finger contact for original-task diagnostic labels only."""
    env = wrapper.env
    gripper = env.robots[0].gripper
    objects = {}
    for name, obj in env.objects_dict.items():
        objects[name] = {
            "dual_finger_contact": bool(env._check_grasp(gripper, obj.contact_geoms)),
            "xyz": np.asarray(env.sim.data.body_xpos[env.obj_body_id[name]]).tolist(),
        }
    from robots.libero.v5_motion_diagnostics import motion_diagnostic
    return {"source": "simulation_diagnostic_only", "objects": objects,
            "contacts": motion_diagnostic(wrapper)["contacts"],
            "sim_time": float(env.sim.data.time)}


def controller_contract(wrapper):
    """Inspect loaded actuator scaling privately, without a control step."""
    contracts = []
    for robot in wrapper.env.robots:
        controllers = getattr(robot, "part_controllers", None)
        if controllers is None:
            controllers = {"controller": robot.controller}
        contracts.append({name: {
            "class": type(controller).__name__,
            **{field: copy.deepcopy(getattr(controller, field))
               for field in ("input_min", "input_max", "output_min", "output_max",
                             "input_ref_frame", "control_delta")
               if hasattr(controller, field)},
        } for name, controller in controllers.items()})
    return {"robots": contracts, "scope": "private_actuator_diagnostic_only"}


def attach_branch_state(wrapper):
    """Attach private state and predicate methods in the original-task worker."""
    wrapper.v5_actuator_state = types.MethodType(actuator_state, wrapper)
    wrapper.v5_restore_actuators = types.MethodType(restore_actuators, wrapper)
    wrapper.v5_storage_open = types.MethodType(storage_open, wrapper)
    wrapper.v5_reference_geometry = types.MethodType(reference_geometry, wrapper)
    wrapper.v5_grasp_contacts = types.MethodType(grasp_contacts, wrapper)
    wrapper.v5_controller_contract = types.MethodType(controller_contract, wrapper)
    from robots.libero.v5_grasp_truth import contact_sample, measure_hold
    def grasp_reference(self, name):
        return contact_sample(self.env, name)
    wrapper.v5_grasp_reference = types.MethodType(grasp_reference, wrapper)
    wrapper.v5_measure_grasp_hold = types.MethodType(measure_hold, wrapper)
    return wrapper
