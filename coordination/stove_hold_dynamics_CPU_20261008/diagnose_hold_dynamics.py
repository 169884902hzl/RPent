"""Fixed-action CPU stove dynamics diagnosis; private sensors never control execution."""

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import types


ROOT = "/public/home/sunyihan/rpent_libero_eval"
BASELINE = {"path": ROOT + "/results/harness_v5/control580_saved_prefix_CPU_20261008/job4538_part2_replay_r1/manifest.json",
    "sha256": "7eb5e2dd17626a7e17565404f408092c724261d40c4b85b3bc8ef6b96eebc1bd"}
HELPER = {"path": ROOT + "/scripts/replay_v5_stove_saved_prefix_CPU_20261008.py",
    "sha256": "69162da69a14246d0bf8aa65b6fe8cc20725e86cfc75728b339ee62f5120df6b"}


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(reference):
    if identity(reference["path"]) != {key: reference[key] for key in ("path", "sha256")}:
        raise ValueError("Pinned diagnostic input changed: " + reference["path"])
    return Path(reference["path"])


def load(reference):
    return json.loads(pinned(reference).read_text())


def module_at(name, reference):
    spec = importlib.util.spec_from_file_location(name, pinned(reference))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(record):
    return json.dumps(record, ensure_ascii=False, allow_nan=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard" or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        parser.error("Require LIBERO_TYPE=standard and CUDA_VISIBLE_DEVICES=''")
    baseline = load(BASELINE)
    if not baseline["physical_prefix_verified"] or not baseline["suffix_comparison_executed"]:
        raise ValueError("The previously exact physical prefix is required")
    helper = module_at("stove_dynamics_pinned_helper", HELPER)
    packet_ref = baseline["packet"]
    packet = load(packet_ref)
    if packet["original_episode"] != {"suite": "libero_goal", "task": 7, "seed": 2}:
        raise ValueError("Only previously visited train init2; validation init3/4 are excluded")
    import numpy as np
    import torch
    import mujoco
    from libero.libero.envs.env_wrapper import ControlEnv
    from libero.libero.envs.objects import articulated_objects
    from libero.libero.envs.object_states import ObjectState
    from libero.libero.envs.predicates.base_predicates import TurnOff, TurnOn
    from robosuite.controllers.parts.arm.osc import OperationalSpaceController
    from robosuite.environments.base import MujocoEnv
    from robosuite.models.grippers.panda_gripper import PandaGripper

    if identity(inspect.getfile(ControlEnv)) != baseline["source_files"]["ControlEnv"]:
        raise ValueError("Original environment wrapper changed since exact replay")
    reset = helper.module_at("stove_dynamics_reset", baseline["source_files"]["reset_adapter"])
    state_file = pinned(packet["original_init_file"])
    states = torch.load(state_file, map_location="cpu", weights_only=False)
    rawstate = np.asarray(states[2], dtype="<f8", order="C")
    if hashlib.sha256(rawstate.tobytes()).hexdigest() != packet["original_raw_state_sha256"]:
        raise ValueError("Original train state changed")
    actions = np.load(pinned(packet["actions"]), allow_pickle=False)
    checkpoints = load(packet["checkpoints"])
    if (actions.shape != (900, 7) or actions.dtype != np.dtype("<f4")
            or hashlib.sha256(actions.tobytes()).hexdigest() != packet["action_bytes_sha256"]):
        raise ValueError("Complete exact 900-control prefix is required")
    bddl = pinned(packet["original_bddl"])
    stove_xml = Path(articulated_objects.absolute_path) / "assets/articulated_objects/flat_stove.xml"
    source_refs = {"producer": identity(__file__), "helper": HELPER,
        "original_stove_xml": identity(stove_xml),
        **{name: identity(inspect.getfile(cls)) for name, cls in {
            "FlatStove": articulated_objects.FlatStove, "ObjectState": ObjectState,
            "TurnOff": TurnOff, "TurnOn": TurnOn,
            "OperationalSpaceController": OperationalSpaceController, "MujocoEnv": MujocoEnv,
            "PandaGripper": PandaGripper}.items()}}
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"schema": "stove-hold-dynamics-fixed-CPU-plan/1", "baseline": BASELINE,
        "packet": packet_ref, "source_files": source_refs,
        "original_episode": packet["original_episode"], "original_state_sha256": packet["original_raw_state_sha256"],
        "reset_controls": 15, "reset_action": [0, 0, 0, 0, 0, 0, -1],
        "prefix_controls": 900, "prefix_action_bytes_sha256": packet["action_bytes_sha256"],
        "suffix_controls": 20, "conditions": {"release": [0, 0, 0, 0, 0, 0, -1],
            "neutral_no_release": [0, 0, 0, 0, 0, 0, 0]},
        "private_data": "passively recorded each actual control; last prefix control and fixed suffix also record internal physics steps",
        "private_labels_control_actions_or_stop": False, "runtime_or_recipe_modified": False,
        "confirmation_or_validation_data_read": False, "PRO_read": False,
        "training_allowed": False, "GPU_or_policy_or_renderer_used": False}
    plan_path = args.output / "fixed_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    report = {"schema": "stove-hold-dynamics-CPU-run/1", "fixed_plan": identity(plan_path),
        "status": "running", "conditions": [], "physics_executed": False,
        "private_labels_control_actions_or_stop": False, "training_allowed": False}
    report_path = args.output / "manifest.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    save()
    try:
        for condition, action_values in plan["conditions"].items():
            directory = args.output / condition
            directory.mkdir()
            public_path = directory / "public_controls.jsonl"
            private_path = directory / "private_control_dynamics.jsonl"
            substep_path = directory / "private_suffix_physics_steps.jsonl"
            wrapper = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=False,
                has_renderer=False, has_offscreen_renderer=False, camera_names=[],
                ignore_done=True, horizon=10015)
            reset.attach_reset_seed(wrapper)
            wrapper.seed(2)
            wrapper.reset()
            wrapper.set_init_state(rawstate)
            sim, model, data = wrapper.sim, wrapper.sim.model, wrapper.sim.data
            obj = wrapper.env.fixtures_dict["flat_stove_1"]
            if len(obj.joints) != 1:
                raise ValueError("Expected the one original stove hinge")
            joint_name = obj.joints[0]
            jid = model.joint_name2id(joint_name)
            qid = int(model.jnt_qposadr[jid])
            vid = int(model.jnt_dofadr[jid])
            bid = int(model.jnt_bodyid[jid])
            raw_model, raw_data = model._model, data._data
            joint = {"name": joint_name, "joint_id": jid, "qpos_index": qid, "dof_index": vid,
                "body": model.body_id2name(bid), "range_rad": model.jnt_range[jid].tolist(),
                "limited": int(model.jnt_limited[jid]), "axis_local": model.jnt_axis[jid].tolist(),
                "damping": float(model.dof_damping[vid]), "frictionloss": float(model.dof_frictionloss[vid]),
                "armature": float(model.dof_armature[vid]), "stiffness": float(model.jnt_stiffness[jid]),
                "spring_reference": float(model.qpos_spring[qid]), "margin": float(model.jnt_margin[jid]),
                "solref_limit": model.jnt_solref[jid].tolist(), "solimp_limit": model.jnt_solimp[jid].tolist(),
                "sim_timestep_s": float(model.opt.timestep), "control_timestep_s": wrapper.env.control_timestep,
                "lite_physics": bool(wrapper.env.lite_physics), "jacobian_option": int(model.opt.jacobian)}
            robot = wrapper.env.robots[0]
            controller = next(iter(robot.part_controllers.values()))
            controller_info = {name: str(getattr(controller, name, None)) for name in
                ("input_type", "input_ref_frame", "_goal_update_mode", "impedance_mode")}
            (directory / "compiled_joint_and_controller.json").write_text(json.dumps({"joint": joint,
                "arm_controller_class": type(controller).__name__, "controller": controller_info,
                "private_diagnostic_only": True}, indent=2) + "\n")
            context = {"phase": "initial", "phase_control": 0, "actual_control": 0, "physics_substep": 0}
            private_substeps = []

            def private_sample():
                contacts = []
                for contact_id in range(data.ncon):
                    contact = data.contact[contact_id]
                    bodies = [int(model.geom_bodyid[int(g)]) for g in (contact.geom1, contact.geom2)]
                    names = [model.body_id2name(b) or "" for b in bodies]
                    if not any(name.startswith("flat_stove_1") for name in names):
                        continue
                    wrench = np.zeros(6)
                    mujoco.mj_contactForce(raw_model, raw_data, contact_id, wrench)
                    contacts.append({"contact_id": contact_id,
                        "geom_ids": [int(contact.geom1), int(contact.geom2)],
                        "geom_names": [model.geom_id2name(int(g)) for g in (contact.geom1, contact.geom2)],
                        "body_names": names, "involves_knob": bid in bodies,
                        "involves_robot": any(name.startswith("robot0") or name.startswith("gripper0") for name in names),
                        "distance_m": float(contact.dist), "position_world_m": contact.pos.tolist(),
                        "frame_rows_world": np.asarray(contact.frame).reshape(3, 3).tolist(),
                        "contactframe_force_torque": wrench.tolist(), "efc_address": int(contact.efc_address)})
                constraints = []
                jacobian = np.asarray(data.efc_J)
                dense = jacobian.size == data.nefc * model.nv
                if dense:
                    jacobian = jacobian.reshape(data.nefc, model.nv)
                for row in range(data.nefc):
                    ctype, object_id = int(data.efc_type[row]), int(data.efc_id[row])
                    # Record all constraints with a nonzero knob Jacobian and
                    # the knob's own limit. No constraint is changed or disabled.
                    coefficient = float(jacobian[row, vid]) if dense else None
                    is_limit = ctype == int(mujoco.mjtConstraint.mjCNSTR_LIMIT_JOINT) and object_id == jid
                    if not is_limit and (coefficient is None or coefficient == 0):
                        continue
                    force = float(data.efc_force[row])
                    constraints.append({"type": ctype, "object_id": object_id, "is_knob_limit": is_limit,
                        "position": float(data.efc_pos[row]), "velocity": float(data.efc_vel[row]),
                        "force": force, "knob_jacobian": coefficient,
                        "knob_generalized_torque": coefficient * force if coefficient is not None else None})
                return {**context, "sim_time_s": float(data.time), "qpos_rad": float(data.qpos[qid]),
                    "qvel_rad_s": float(data.qvel[vid]), "qacc_rad_s2": float(data.qacc[vid]),
                    "qfrc_passive": float(data.qfrc_passive[vid]), "qfrc_bias": float(data.qfrc_bias[vid]),
                    "qfrc_actuator": float(data.qfrc_actuator[vid]), "qfrc_applied": float(data.qfrc_applied[vid]),
                    "qfrc_constraint": float(data.qfrc_constraint[vid]),
                    "constraint_jacobian_dense": dense, "constraints": constraints, "contacts": contacts,
                    "native_visual_burner_boolean": bool(obj.object_properties["vis_site_names"]["burner"][1]),
                    "private_diagnostic_only": True,
                    "force_timing": "last existing solver evaluation; no extra forward/recompute inserted"}

            step_method = "step2" if wrapper.env.lite_physics else "step"
            original_step = getattr(sim, step_method)

            def monitored_physics(self):
                result = original_step()
                if context["phase"] == "suffix" or (context["phase"] == "prefix" and context["phase_control"] == 900):
                    context["physics_substep"] += 1
                    private_substeps.append(private_sample())
                return result

            setattr(sim, step_method, types.MethodType(monitored_physics, sim))
            observations, private_controls, verified = [], [], 0

            def physical_control(action, phase, index):
                context.update(phase=phase, phase_control=index, actual_control=context["actual_control"] + 1,
                    physics_substep=0)
                raw, _, _, _ = wrapper.step(action)
                eef = np.asarray(raw["robot0_eef_pos"], dtype=np.float32)
                grip = np.asarray(raw["robot0_gripper_qpos"], dtype=np.float32)
                opening = float(abs(grip[0]) + abs(grip[1]))
                observations.append({"phase": phase, "phase_control": index, "actual_control": context["actual_control"],
                    "sim_time_s": float(data.time), "action": np.asarray(action).tolist(),
                    "eef_xyz_m": eef.tolist(), "gripper_opening_m": opening,
                    "robot_proprioception_only": True})
                private_controls.append(private_sample())
                report["physics_executed"] = True
                return eef, opening

            try:
                settling = np.array([0, 0, 0, 0, 0, 0, -1], dtype=np.float64)
                for index in range(15):
                    physical_control(settling, "reset_settle", index + 1)
                for index, action in enumerate(actions):
                    eef, opening = physical_control(action, "prefix", index + 1)
                    if (index + 1) % 5 == 0:
                        expected = checkpoints[(index + 1) // 5 - 1]
                        chunk = actions[index - 4:index + 1]
                        if (hashlib.sha256(chunk.tobytes()).hexdigest() != expected["action_chunk_sha256"]
                                or not np.array_equal(eef, np.asarray(expected["final_eef_pos"], dtype=np.float32))
                                or opening != expected["gripper_opening"]):
                            raise ValueError("Instrumented prefix differs at control " + str(index + 1))
                        verified += 1
                suffix = np.asarray(action_values, dtype=np.float32)
                for index in range(20):
                    physical_control(suffix, "suffix", index + 1)
                # Private truth is consulted after all fixed controls are done.
                official_off = bool(wrapper.env._eval_predicate(["turnoff", "flat_stove_1"]))
                predicate_zero_threshold = max(obj.object_properties["articulation"]["default_turnoff_ranges"])
                for row in private_controls + private_substeps:
                    row["offline_turn_off_from_source_predicate"] = row["qpos_rad"] < predicate_zero_threshold
                public_path.write_text("\n".join(dump(row) for row in observations) + "\n")
                private_path.write_text("\n".join(dump(row) for row in private_controls) + "\n")
                substep_path.write_text("\n".join(dump(row) for row in private_substeps) + "\n")
                result = {"condition": condition, "controls_recorded": len(observations),
                    "prefix_checkpoints_exact": verified, "private_substeps_recorded": len(private_substeps),
                    "public_controls": identity(public_path), "private_dynamics": identity(private_path),
                    "private_physics_substeps": identity(substep_path),
                    "compiled_joint_and_controller": identity(directory / "compiled_joint_and_controller.json"),
                    "final_qpos_rad": float(data.qpos[qid]), "final_official_turn_off": official_off,
                    "official_predicate_matches_raw_qpos_formula": official_off == (float(data.qpos[qid]) < predicate_zero_threshold)}
                report["conditions"].append(result)
                save()
            finally:
                setattr(sim, step_method, original_step)
                wrapper.close()
        report["status"] = "completed"
        save()
        print(json.dumps({"manifest": identity(report_path), "conditions": report["conditions"]}, indent=2))
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        save()
        raise


if __name__ == "__main__":
    main()
