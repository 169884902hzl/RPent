"""Private isolated counterfactual for grasp_truth_v3_1153_20261009.

This module never runs in the policy process. MuJoCo's contact callback is
process-global, so the caller starts a separate interpreter for a batch of
complete integration snapshots.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


VERSION = "isolated-target-gripper-removal/1"
REGISTRATION = "grasp_truth_v3_1153_20261009"
LOCK_TOLERANCE_M = 0.001
LOCK_TOLERANCE_RAD = 0.001


def unknown(reason: str, **details) -> dict:
    return {"version": VERSION, "registration_id": REGISTRATION,
            "value": None, "status": "unknown", "reason": reason,
            "source": "simulation_diagnostic_only", **details}


def descendants(model, root: int) -> list[int]:
    result = []
    for body in range(model.nbody):
        ancestor = body
        while ancestor and ancestor != root:
            ancestor = int(model.body_parentid[ancestor])
        if ancestor == root:
            result.append(body)
    return result


def mass_weighted_com(model, data, bodies: list[int]) -> np.ndarray:
    masses = np.asarray(model.body_mass[bodies], dtype=float)
    if not np.isfinite(masses).all() or masses.sum() <= 0:
        raise ValueError("missing_positive_target_mass")
    return (np.asarray(data.xipos[bodies]) * masses[:, None]).sum(axis=0) / masses.sum()


def default_mask_filter(model, geom1: int, geom2: int) -> bool:
    """MuJoCo 3.3 engine_collision_driver.c filterBitmask (lines 102–104).

    Native body/parent/exclusion filters are applied before the callback;
    this preserves the bitmask filter that the callback otherwise replaces.
    Explicit pairs bypass this filter, as they do in the native engine.
    """
    return not ((int(model.geom_contype[geom1]) & int(model.geom_conaffinity[geom2]))
                or (int(model.geom_contype[geom2]) & int(model.geom_conaffinity[geom1])))


def evaluate(model, state: np.ndarray, metadata: dict) -> dict:
    import mujoco

    spec = int(mujoco.mjtState.mjSTATE_INTEGRATION)
    if metadata.get("state_spec") != spec or state.shape != (mujoco.mj_stateSize(model, spec),):
        return unknown("incomplete_integration_state")
    if not np.isfinite(state).all():
        return unknown("nonfinite_integration_state")
    targets = set(metadata.get("target_geom_ids", []))
    gripper = set(metadata.get("gripper_geom_ids", []))
    bodies = metadata.get("target_body_ids", [])
    locked_bodies = metadata.get("robot_body_ids", [])
    qpos_ids = metadata.get("robot_qpos_ids", [])
    dof_ids = metadata.get("robot_dof_ids", [])
    target_dofs = metadata.get("target_free_dof_ids", [])
    if (not targets or not gripper or targets & gripper or not bodies
            or not locked_bodies or not qpos_ids or not dof_ids
            or len(target_dofs) != 6 or set(target_dofs) & set(dof_ids)):
        return unknown("missing_or_conflicting_target_gripper_lock_geometry")
    target_root = metadata.get("target_root_body_id")
    robot_root = metadata.get("robot_root_body_id")
    gripper_roots = metadata.get("gripper_root_body_ids", [])
    if target_root is None or robot_root is None or not gripper_roots:
        return unknown("missing_geometry_subtree_identity")
    actual_targets = {i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in descendants(model, target_root)}
    actual_gripper_bodies = {b for root in gripper_roots for b in descendants(model, root)}
    actual_gripper = {i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in actual_gripper_bodies}
    if targets != actual_targets or gripper != actual_gripper or set(bodies) != set(descendants(model, target_root)):
        return unknown("incomplete_target_or_gripper_subtree_geometry")
    if set(locked_bodies) != set(descendants(model, robot_root)):
        return unknown("incomplete_robot_subtree_lock")
    if metadata.get("complete_gripper_geometry") is not True:
        return unknown("incomplete_gripper_geometry")
    if metadata.get("unserialised_callback_present"):
        return unknown("source_callback_cannot_be_reproduced")
    if model.opt.enableflags & int(mujoco.mjtEnableBit.mjENBL_OVERRIDE):
        return unknown("collision_override_prevents_explicit_pair_filter")

    def target_gripper(a, b):
        return ((a in targets and b in gripper) or (b in targets and a in gripper))

    def contact_filter(m, d, a, b):
        return int(target_gripper(a, b) or default_mask_filter(m, a, b))

    data = mujoco.MjData(model)
    old_callback = mujoco.get_mjcb_contactfilter()
    pair_ids = [i for i in range(model.npair)
                if target_gripper(int(model.pair_geom1[i]), int(model.pair_geom2[i]))]
    saved_margins = np.asarray(model.pair_margin).copy()
    saved_gaps = np.asarray(model.pair_gap).copy()
    saved_masks = (np.asarray(model.geom_contype).copy(), np.asarray(model.geom_conaffinity).copy())
    try:
        mujoco.mj_setState(model, data, state, spec)
        mujoco.mj_forward(model, data)
        original_qpos = np.asarray(data.qpos[qpos_ids]).copy()
        original_positions = np.asarray(data.xpos[locked_bodies]).copy()
        original_rotations = np.asarray(data.xmat[locked_bodies]).reshape(-1, 3, 3).copy()
        before = mass_weighted_com(model, data, bodies)
        # Only the target starts from zero velocity. Robot velocity is zeroed
        # each integration step as part of the explicitly registered lock.
        data.qvel[target_dofs] = 0
        mujoco.set_mjcb_contactfilter(contact_filter)
        # Explicit pairs bypass contactfilter. A negative detection margin
        # removes these pairs alone without modifying native collision masks.
        for pair in pair_ids:
            model.pair_margin[pair] = -1e6
            model.pair_gap[pair] = 0
        max_drop = 0.0
        max_position_drift = 0.0
        max_angle_drift = 0.0
        surviving_removed_contacts = 0
        samples = []
        step_count = math.ceil(0.5 / float(model.opt.timestep))
        for step in range(step_count):
            data.qpos[qpos_ids] = original_qpos
            data.qvel[dof_ids] = 0
            mujoco.mj_forward(model, data)
            mujoco.mj_step(model, data)
            # Recompute positions before measuring drift; mj_step's derived
            # kinematics describe the preceding state until mj_forward.
            mujoco.mj_forward(model, data)
            drift = np.linalg.norm(np.asarray(data.xpos[locked_bodies]) - original_positions, axis=1)
            rotations = np.asarray(data.xmat[locked_bodies]).reshape(-1, 3, 3)
            rel = np.einsum("bij,bkj->bik", rotations, original_rotations)
            angles = np.arccos(np.clip((np.trace(rel, axis1=1, axis2=2) - 1) / 2, -1, 1))
            max_position_drift = max(max_position_drift, float(drift.max()))
            max_angle_drift = max(max_angle_drift, float(angles.max()))
            if max_position_drift > LOCK_TOLERANCE_M or max_angle_drift > LOCK_TOLERANCE_RAD:
                return unknown("robot_lock_drift_exceeds_tolerance",
                               max_robot_drift_m=max_position_drift,
                               max_robot_angle_drift_rad=max_angle_drift)
            data.qpos[qpos_ids] = original_qpos
            data.qvel[dof_ids] = 0
            mujoco.mj_forward(model, data)
            surviving_removed_contacts += sum(
                target_gripper(int(data.contact[i].geom1), int(data.contact[i].geom2))
                for i in range(data.ncon))
            com = mass_weighted_com(model, data, bodies)
            max_drop = max(max_drop, float(before[2] - com[2]))
            samples.append({"elapsed_s": (step + 1) * float(model.opt.timestep),
                            "com_xyz": com.tolist()})
        if surviving_removed_contacts:
            return unknown("target_gripper_contact_removal_incomplete")
        if (not np.array_equal(saved_masks[0], model.geom_contype)
                or not np.array_equal(saved_masks[1], model.geom_conaffinity)):
            return unknown("native_collision_masks_changed")
        return {"version": VERSION, "registration_id": REGISTRATION,
                "value": bool(max_drop < 0.01), "status": "known",
                "reason": "external_support_remains" if max_drop < 0.01 else "outside_contact_not_load_bearing",
                "max_downward_com_displacement_m": max_drop,
                "drop_threshold_m": 0.01, "duration_s": step_count * float(model.opt.timestep),
                "robot_lock": "qpos_projection_each_integration_step_with_drift_check",
                "max_robot_drift_m": max_position_drift,
                "max_robot_angle_drift_rad": max_angle_drift,
                "lock_tolerance_m": LOCK_TOLERANCE_M, "lock_tolerance_rad": LOCK_TOLERANCE_RAD,
                "removed_explicit_pair_ids": pair_ids,
                "target_gripper_contacts_after_removal": surviving_removed_contacts,
                "native_collision_masks_preserved": True, "pair_coverage_complete": True,
                "target_initial_velocity_zeroed": True,
                "com_source": "mass_weighted_target_subtree_xipos",
                "counterfactual_samples": samples,
                "source": "simulation_diagnostic_only"}
    except Exception as exc:
        return unknown("counterfactual_error:" + repr(exc))
    finally:
        model.pair_margin[:] = saved_margins
        model.pair_gap[:] = saved_gaps
        mujoco.set_mjcb_contactfilter(old_callback)


def main() -> None:
    import mujoco

    packet = json.loads(Path(sys.argv[1]).read_text())
    model_file = Path(packet["model_path"])
    if hashlib.sha256(model_file.read_bytes()).hexdigest() != packet["model_sha256"]:
        raise ValueError("counterfactual model identity mismatch")
    model = mujoco.MjModel.from_binary_path(str(model_file))
    states = np.load(packet["states_path"], allow_pickle=False)["states"]
    results = []
    for state in states:
        result = evaluate(model, state, packet["metadata"])
        results.append({**result, "model_sha256": packet["model_sha256"],
                        "integration_state_sha256": hashlib.sha256(state.astype("<f8").tobytes()).hexdigest(),
                        "worker_pid": __import__("os").getpid()})
    Path(packet["output_path"]).write_text(json.dumps(results) + "\n")


if __name__ == "__main__":
    main()
