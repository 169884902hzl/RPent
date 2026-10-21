# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Capture actuator and fixture state omitted by MuJoCo's flat snapshot."""

from __future__ import annotations

import copy
import ctypes
from functools import lru_cache
import hashlib
from pathlib import Path
import pickle
import random
import types

import numpy as np

DATA_FIELDS = ("ctrl", "qacc_warmstart", "mocap_pos", "mocap_quat", "userdata", "qfrc_applied", "xfrc_applied")
CONTROLLER_FIELDS = ("goal_pos", "goal_ori", "goal_qpos", "goal_qvel", "_goal_update_mode", "ori_ref", "relative_ori")
OBSERVABLE_FIELDS = ("_sampling_timestep", "_enabled", "_active", "_time_since_last_sample",
                     "_current_delay", "_current_observed_value", "_sampled")


def _plain_state(value):
    if value is None or isinstance(value, (str, bool, int, float, np.generic)):
        return True
    if isinstance(value, np.ndarray):
        return value.dtype.kind != 'O'
    if isinstance(value, (list, tuple)):
        return all(_plain_state(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, (str, int)) and _plain_state(item) for key, item in value.items())
    return False


def captured_projection(current, reference):
    """Compare every saved field of a legacy snapshot without inventing extras.

    New complete snapshots must still use full identity, without projection.
    The caller records that older snapshots omitted integration/phase state.
    """
    if isinstance(reference,dict):
        missing=set(reference)-set(current)
        if missing:
            raise ValueError('captured snapshot fields missing: '+str(sorted(missing)))
        return {key:captured_projection(current[key],value) for key,value in reference.items()}
    if isinstance(reference,(list,tuple)):
        if len(current)!=len(reference):
            raise ValueError('captured snapshot sequence shape changed')
        return [captured_projection(a,b) for a,b in zip(current,reference)]
    return current


def integration_state(env):
    """Capture MuJoCo's full integration vector, including solver warm start."""
    # Unit-test sensor doubles have no native simulator. Real robosuite uses
    # these native handles, as does the existing private grasp truth worker.
    if not hasattr(env.sim.model, '_model'):
        return None
    import mujoco
    model, data = env.sim.model._model, env.sim.data._data
    spec = int(mujoco.mjtState.mjSTATE_INTEGRATION)
    values = np.empty(mujoco.mj_stateSize(model, spec), dtype=np.float64)
    mujoco.mj_getState(model, data, values, spec)
    return {'spec': spec, 'values': values,
            'sha256': hashlib.sha256(values.astype('<f8').tobytes()).hexdigest()}


def restore_integration(env, saved):
    """Restore every integration field; legacy snapshots remain identifiable."""
    if saved is None:
        return
    import mujoco
    model, data = env.sim.model._model, env.sim.data._data
    spec = int(mujoco.mjtState.mjSTATE_INTEGRATION)
    values = np.asarray(saved['values'], dtype=np.float64)
    if saved['spec'] != spec or values.shape != (mujoco.mj_stateSize(model, spec),):
        raise ValueError('branch integration state specification changed')
    if hashlib.sha256(values.astype('<f8').tobytes()).hexdigest() != saved['sha256']:
        raise ValueError('branch integration state checksum mismatch')
    mujoco.mj_setState(model, data, values, spec)


def native_data_state(env):
    """Retain the native step's derived contacts/transforms as well as qpos.

    mj_step leaves contacts and kinematics at its solver evaluation phase.
    mj_forward at the final integrated qpos can change an On predicate with
    zero controls. The integration vector alone does not encode that phase.
    """
    model = getattr(env.sim.model, '_model', None)
    if not hasattr(model, 'nq'):
        return None
    import mujoco
    raw = pickle.dumps(env.sim.data._data, protocol=5)
    return {'version': 'mujoco-native-data/1', 'mujoco_version': mujoco.__version__,
        'values': np.frombuffer(raw, dtype=np.uint8).copy(),
        'sha256': hashlib.sha256(raw).hexdigest()}


@lru_cache(maxsize=1)
def _native_copy_data():
    """Bind the installed MuJoCo C API; 3.3 omits its Python wrapper."""
    import mujoco
    libraries = list(Path(mujoco.__file__).parent.glob('libmujoco.so*'))
    if len(libraries) != 1:
        raise RuntimeError('expected the installed MuJoCo shared library')
    function = ctypes.CDLL(str(libraries[0])).mj_copyData
    # mujoco.h: mjData* mj_copyData(mjData*, const mjModel*, const mjData*).
    function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    function.restype = ctypes.c_void_p
    return function


def restore_native_data(env, saved):
    """Copy the saved native buffers in place, retaining existing array views."""
    if saved is None:
        return
    import mujoco
    if saved['version'] != 'mujoco-native-data/1' or saved['mujoco_version'] != mujoco.__version__:
        raise ValueError('branch native MuJoCo version changed')
    raw = np.asarray(saved['values'], dtype=np.uint8).tobytes()
    if hashlib.sha256(raw).hexdigest() != saved['sha256']:
        raise ValueError('branch native data checksum mismatch')
    source = pickle.loads(raw)
    target, model = env.sim.data._data, env.sim.model._model
    if any(getattr(source, key).shape != getattr(target, key).shape
            for key in ('qpos', 'qvel', 'ctrl', 'xpos', 'geom_xpos', 'site_xpos')):
        raise ValueError('branch native model dimensions changed')
    if _native_copy_data()(target._address, model._address, source._address) != target._address:
        raise RuntimeError('native branch data copy failed')


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
            # Include numeric controller caches/phase flags as well as goals.
            # Simulator references and callables are resources, not state.
            fields = {field: value for field, value in vars(controller).items() if _plain_state(value)}
            fields.update({field:getattr(controller,field) for field in CONTROLLER_FIELDS if hasattr(controller,field)})
            controls[name] = copy.deepcopy(fields)
        robots.append({"grippers": {name: {"type": type(gripper).__name__, "current_action": copy.deepcopy(gripper.current_action)}
                                     for name, gripper in grippers.items()}, "controllers": controls})
    return {"integration": integration_state(env), "native_data": native_data_state(env),
            "model": {field: np.array(getattr(env.sim.model, field), copy=True)
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
    restore_integration(env, saved.get('integration'))
    env.sim.forward()
    observations = restore_observation_state(wrapper, saved.get('observation_state'))
    # forward() rebuilds solver input. Keep its captured integration warmstart
    # after observations, as required by the strict complete-state identity.
    if 'qacc_warmstart' in saved['data']:
        env.sim.data.qacc_warmstart[:] = saved['data']['qacc_warmstart']
    # mj_forward/observation code can change integration warm-start fields.
    # Retain its derived transforms, then restore the exact captured vector.
    restore_integration(env, saved.get('integration'))
    # Undo the forward/observation solver-phase change too. Exact native task
    # predicates must survive restoration without turning an old success into
    # a latch or integrating another control.
    restore_native_data(env, saved.get('native_data'))
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
