"""Private original-task grasp metrology, never a runtime decision input."""

from __future__ import annotations

import numpy as np


GRIPPER_GEOMETRY_VERSION = "gripper_geometry/1"
GRIPPER_GEOMETRY_SOURCE = "component.contact_geoms+component.important_geoms"
SUPPORT_RULE_V2 = "all_current_non_gripper_contacts/2"
SUPPORT_RULE_V3 = "grasp_truth_v3_1153_20261009/isolated-gripper-removal/1"
V3_CLEARANCE_M = 0.03
V3_RELATIVE_DISPLACEMENT_M = 0.01
V3_DURATION_S = 0.5
V3_MIN_SAMPLES = 11
V3_MAX_SAMPLE_GAP_S = 0.075
INITIAL_SUPPORT_VERSION = "initial-contact-geometries/1-dev"


def initial_contact_support(contacts: list[dict], sim_time: float) -> dict:
    """Fixed support height from actual initial contacts, never an asset table.

    Sloped or stepped supports need not share one horizontal contact plane.
    Use the highest upward contact; the existing 3 cm whole-object clearance
    remains required above it. Missing contacts stay missing.
    """
    upward = [c for c in contacts if c['normal_on_target'][2] > 0
              and np.isfinite(c['contact_xyz']).all()]
    evidence = {'version': INITIAL_SUPPORT_VERSION,
                'source': 'simulation_initial_contact_geometries_diagnostic_only',
                'support_geom_ids': sorted({c['support_geom'] for c in upward}),
                'all_initial_contact_geom_ids': sorted({c['support_geom'] for c in contacts}),
                'captured_sim_time': float(sim_time), 'contacts': contacts,
                'height_rule': 'highest_upward_initial_contact',
                'registration_table_used': False}
    return {'original_support_plane_z_m': max(c['contact_xyz'][2] for c in upward)
            if upward else None, 'original_support_plane_evidence': evidence}


def object_lower_extent(env, obj) -> float:
    """Compute the collision geometry's lowest world point from simulator truth."""
    model, data = env.sim.model, env.sim.data
    lower = []
    for name in obj.contact_geoms:
        gid = model.geom_name2id(name)
        kind = int(model.geom_type[gid])
        size = np.asarray(model.geom_size[gid], dtype=float)
        rotation = np.asarray(data.geom_xmat[gid], dtype=float).reshape(3, 3)
        centre = np.asarray(data.geom_xpos[gid], dtype=float)
        if kind == 2:  # sphere
            radius = size[0]
        elif kind == 3:  # capsule: axis-z segment plus sphere
            radius = abs(rotation[2, 2]) * size[1] + size[0]
        elif kind == 4:  # ellipsoid
            radius = np.linalg.norm(rotation[2] * size)
        elif kind == 5:  # cylinder
            radius = np.linalg.norm(rotation[2, :2]) * size[0] + abs(rotation[2, 2]) * size[1]
        elif kind == 6:  # box
            radius = np.abs(rotation[2]) @ size
        elif kind == 7:  # mesh; MuJoCo vertices are in the geom-local frame
            mesh = int(model.geom_dataid[gid])
            start, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
            vertices = np.asarray(model.mesh_vert[start:start + count], dtype=float)
            lower.append(float(centre[2] + (vertices @ rotation[2]).min()))
            continue
        else:
            raise ValueError(f"unsupported grasp collision geometry type {kind}: {name}")
        lower.append(float(centre[2] - radius))
    if not lower:
        raise ValueError("target object has no collision geometry")
    return min(lower)


def _tcp_pose(env):
    """Return public TCP pose from the simulator kinematic state for labels only."""
    model, data = env.sim.model, env.sim.data
    # A missing TCP site is missing evidence; never substitute a body origin.
    site_id = None
    site_names = ["grip_site", "robot0_grip_site", "right_grip_site"]
    try:
        site_names.extend(model.site_id2name(i) for i in range(int(model.nsite))
                          if "grip_site" in (model.site_id2name(i) or ""))
    except Exception:
        pass
    for site_name in site_names:
        try:
            site_id = int(model.site_name2id(site_name))
            break
        except Exception:
            continue
    if site_id is not None:
        return (np.asarray(data.site_xpos[site_id], dtype=float).copy(),
                np.asarray(data.site_xmat[site_id], dtype=float).reshape(3, 3).copy(),
                "simulation_tcp_site")
    return None, None, None

def _target_com(env, name: str):
    """Return mass-weighted target subtree COM, never a body-origin proxy."""
    try:
        from robots.libero.v5_grasp_support_worker import descendants, mass_weighted_com

        body_id = int(env.obj_body_id[name])
        model, data = env.sim.model._model, env.sim.data._data
        return mass_weighted_com(model, data, descendants(model, body_id))
    except Exception:
        return None

def _tcp_relative_com(env, name: str):
    com = _target_com(env, name)
    tcp_xyz, tcp_rot, source = _tcp_pose(env)
    if com is None or tcp_xyz is None or tcp_rot is None:
        return None, None, None
    relative = tcp_rot.T @ (com - tcp_xyz)
    return com, tcp_xyz, {"relative_com_tcp": relative.tolist(),
                          "tcp_rotation_world": tcp_rot.tolist(),
                          "source": source}

def contact_sample(env, name: str) -> dict:
    """Read target/finger and support contacts, without advancing physics."""
    obj = env.objects_dict[name]
    model, data = env.sim.model, env.sim.data
    target = set(obj.contact_geoms)
    gripper = env.robots[0].gripper
    grippers = tuple(gripper.values()) if isinstance(gripper, dict) else (gripper,)
    fingers = {geom for component in grippers
               for key, geoms in component.important_geoms.items()
               if "finger" in key for geom in geoms}
    # Contact geometries include the palm/hand, which can legitimately support
    # a handle against a finger. Keep the old non-finger field unchanged while
    # independently classifying every contact outside the complete gripper.
    contact_geoms = [getattr(component, "contact_geoms", None) for component in grippers]
    gripper_geometry_complete = bool(grippers) and all(geoms is not None for geoms in contact_geoms)
    gripper_geoms = {geom for geoms in contact_geoms if geoms is not None for geom in geoms}
    gripper_geoms.update(geom for component in grippers
                         for geoms in component.important_geoms.values() for geom in geoms)
    touching, finger_contacts, other_contacts = [], [], []
    non_gripper_contacts = []
    support_plane_contacts = []
    initial_support_contacts = []
    for index in range(data.ncon):
        contact = data.contact[index]
        a = model.geom_id2name(int(contact.geom1)) or f"unnamed_geom:{int(contact.geom1)}"
        b = model.geom_id2name(int(contact.geom2)) or f"unnamed_geom:{int(contact.geom2)}"
        if (a in target) == (b in target):
            continue
        other = b if a in target else a
        touching.append({"geom1": a, "geom2": b, "distance_m": float(contact.dist)})
        # Contact normal points from geom1 to geom2. Only near-horizontal
        # upward support under the target provides a fixed plane baseline.
        normal = np.asarray(contact.frame, dtype=float).reshape(3, 3)[0] if hasattr(contact, "frame") else np.zeros(3)
        target_normal = -normal if a in target else normal
        if hasattr(contact, "pos") and other not in gripper_geoms:
            initial_support_contacts.append({"support_geom": other,
                "support_geom_id": int(contact.geom2 if a in target else contact.geom1),
                "contact_xyz": np.asarray(contact.pos, dtype=float).tolist(),
                "normal_on_target": target_normal.tolist(),
                "distance_m": float(contact.dist)})
        if hasattr(contact, "pos") and other not in gripper_geoms and target_normal[2] >= .95:
            support_plane_contacts.append({"support_geom": other,
                "contact_xyz": np.asarray(contact.pos, dtype=float).tolist(),
                "normal_on_target": target_normal.tolist()})
        (finger_contacts if other in fingers else other_contacts).append(other)
        if other not in gripper_geoms:
            non_gripper_contacts.append(other)
    com, tcp_xyz, tcp = _tcp_relative_com(env, name)
    row = {"sim_time": float(data.time), "target": name,
           "lower_extent_m": object_lower_extent(env, obj),
           "finger_contact": bool(finger_contacts),
           "dual_finger_contact": bool(env._check_grasp(gripper, obj.contact_geoms)),
           "finger_geoms": sorted(set(finger_contacts)),
           "other_contact_geoms": sorted(set(other_contacts)), "contacts": touching,
           "all_non_gripper_contact_geoms": (sorted(set(non_gripper_contacts))
                                              if gripper_geometry_complete else None),
           "gripper_geometry": {"version": GRIPPER_GEOMETRY_VERSION,
                                "source": GRIPPER_GEOMETRY_SOURCE,
                                "complete": gripper_geometry_complete,
                                "component_count": len(grippers),
                                "geoms": sorted(gripper_geoms)}}
    if support_plane_contacts:
        heights = [point["contact_xyz"][2] for point in support_plane_contacts]
        if max(heights) - min(heights) <= .002:
            row["original_support_plane_z_m"] = float(np.median(heights))
            row["original_support_plane_evidence"] = {
                "source": "simulation_support_contact_plane_diagnostic_only",
                "support_geom_ids": sorted({point["support_geom"] for point in support_plane_contacts}),
                "captured_sim_time": float(data.time), "contacts": support_plane_contacts}
    row['legacy_horizontal_contact_support'] = {
        'height_m': row.get('original_support_plane_z_m'),
        'evidence': row.get('original_support_plane_evidence')}
    row.update(initial_contact_support(initial_support_contacts, data.time))
    row["settled_original_collision_lower_extent_m"] = row["lower_extent_m"]
    row["support_proxy_source"] = "settled_collision_lower_extent_proxy_not_measured_plane"
    if com is not None and tcp_xyz is not None and tcp is not None:
        row.update({"target_com_xyz": com.tolist(), "tcp_xyz": tcp_xyz.tolist(),
                    "relative_com_tcp": tcp["relative_com_tcp"],
                    "tcp_rotation_world": tcp["tcp_rotation_world"],
                    "tcp_pose_source": tcp["source"]})
    else:
        row["tcp_relative_com_evidence"] = None
    return row


def sustained_grasp(samples: list[dict], reference: dict, duration_s: float = .5) -> dict:
    """Require clearance and finger support throughout a stationary hold.

    The original settled collision lower extent defines the original support
    level. Opposing pads are reported separately: a handle can be supported
    by a finger against the other gripper surface. No visual result is used.
    """
    if not samples:
        raise ValueError("no physical hold samples")
    original_supports = set(reference["other_contact_geoms"])
    checks = [{"elapsed_s": sample["sim_time"] - samples[0]["sim_time"],
               "clearance_m": sample["lower_extent_m"] - reference["lower_extent_m"],
               "finger_contact": sample["finger_contact"],
               "touching_original_support": bool(original_supports & set(sample["other_contact_geoms"]))}
              for sample in samples]
    elapsed = checks[-1]["elapsed_s"]
    return {"success": bool(elapsed + 1e-8 >= duration_s and all(
                row["clearance_m"] >= .03 and row["finger_contact"]
                and not row["touching_original_support"] for row in checks)),
            "duration_s": elapsed, "required_duration_s": duration_s,
            "required_clearance_m": .03, "min_clearance_m": min(row["clearance_m"] for row in checks),
            "samples": len(samples), "checks": checks,
            "reference": "settled_original_collision_lower_extent_and_support_contacts",
            "source": "simulation_diagnostic_only"}


def _v2_sample_check(sample: dict, reference: dict, start_time: float) -> dict:
    """One predicate shared by the v2 first-window and final-window checks."""
    geometry = sample.get("gripper_geometry", {})
    non_gripper = sample.get("all_non_gripper_contact_geoms")
    known = (isinstance(geometry, dict)
             and geometry.get("version") == GRIPPER_GEOMETRY_VERSION
             and geometry.get("source") == GRIPPER_GEOMETRY_SOURCE
             and geometry.get("complete") is True
             and isinstance(geometry.get("geoms"), list)
             and bool(geometry.get("geoms"))
             and isinstance(non_gripper, list))
    clearance = sample["lower_extent_m"] - reference["lower_extent_m"]
    return {"elapsed_s": sample["sim_time"] - start_time,
            "clearance_m": clearance, "finger_contact": sample["finger_contact"],
            "all_non_gripper_contact_geoms": non_gripper if known else None,
            "touching_non_gripper_support": bool(non_gripper) if known else None,
            "qualifies": (bool(clearance >= .03 and sample["finger_contact"] and not non_gripper)
                          if known else None),
            "unknown_reason": None if known else "missing_or_incompatible_v2_contact_fields"}


def sustained_grasp_v2(samples: list[dict], reference: dict, duration_s: float = .5) -> dict:
    """Measure exclusive gripper support; never infer it from legacy samples.

    Any current contact outside component contact/important gripper geometries
    rejects exclusive support, including a destination fixture absent from the
    initial support set. The original function retains its historical rule.
    """
    if not samples:
        raise ValueError("no physical hold samples")
    if duration_s <= 0:
        raise ValueError("positive sustained-grasp duration required")
    checks = [_v2_sample_check(sample, reference, samples[0]["sim_time"]) for sample in samples]
    unknown = [index for index, check in enumerate(checks) if check["qualifies"] is None]
    elapsed = checks[-1]["elapsed_s"]
    success = (None if unknown else bool(elapsed + 1e-8 >= duration_s
                                         and all(check["qualifies"] for check in checks)))
    return {"success": success,
            "status": "unknown" if success is None else "passed" if success else "failed",
            "duration_s": elapsed, "required_duration_s": duration_s,
            "required_clearance_m": .03, "min_clearance_m": min(check["clearance_m"] for check in checks),
            "samples": len(samples), "checks": checks, "unknown_sample_indices": unknown,
            "support_rule": SUPPORT_RULE_V2,
            "reference": "settled_original_collision_lower_extent_and_all_current_non_gripper_contacts",
            "source": "simulation_diagnostic_only"}


def grasp_trace_summary_v2(reference: dict, samples: list[dict], duration_s: float = .5) -> dict:
    """Find first and final sustained windows using exactly the v2 predicate.

    A witnessed known window proves grasp during the skill even if another
    phase is unknown. Without such a window, missing new fields remain unknown.
    A current known support contact rejects the final hold independently of a
    previous successful lift. Unknown gaps cannot be bridged into a true hold.
    """
    if duration_s <= 0:
        raise ValueError("positive sustained-grasp duration required")
    window, first, unknown_count, uncertain_before_window = [], None, 0, False
    for sample in samples:
        check = _v2_sample_check(sample, reference, sample["sim_time"])
        if check["qualifies"] is None:
            unknown_count += 1
            uncertain_before_window = True
            window = []
        elif not check["qualifies"]:
            uncertain_before_window = False
            window = []
        else:
            window.append(sample)
            if sample["sim_time"] - window[0]["sim_time"] + 1e-8 >= duration_s:
                uncertain_before_window = False
                if first is None:
                    first = {"start_sim_time": window[0]["sim_time"],
                             "end_sim_time": sample["sim_time"],
                             "truth": sustained_grasp_v2(window, reference, duration_s)}
    during = True if first else None if unknown_count or not samples else False
    if window:
        final_hold = sustained_grasp_v2(window, reference, duration_s)
        if uncertain_before_window:
            final_hold = {**final_hold, "success": None, "status": "unknown",
                          "unknown_reason": "v2_contact_fields_missing_before_short_final_window"}
        end = final_hold["success"]
    elif samples and _v2_sample_check(samples[-1], reference, samples[-1]["sim_time"])["qualifies"] is False:
        final_hold = sustained_grasp_v2([samples[-1]], reference, duration_s)
        end = False
    else:
        final_hold, end = None, None
    return {"source": "simulation_diagnostic_only", "support_rule": SUPPORT_RULE_V2,
            "control_steps_sampled": len(samples), "reference": reference, "samples": samples,
            "true_sustained_grasp_during_skill": during, "first_sustained_grasp": first,
            "true_sustained_grasp_at_end": end, "final_hold_window": final_hold,
            "unknown_contact_samples": unknown_count,
            "interpretation": "exclusive gripper support; later release/support does not erase an earlier verified window"}


def _v3_sample_check(sample: dict, reference: dict, start_time: float, initial_relative=None) -> dict:
    """Evaluate locked v3; legacy proxy baseline is reported, never upgraded."""
    result = {"elapsed_s": float(sample.get("sim_time", start_time)) - start_time,
              "qualifies": None, "unknown_reason": None}
    plane = reference.get("original_support_plane_z_m")
    provenance = reference.get("original_support_plane_evidence") or {}
    if plane is None or not provenance.get("source") or not provenance.get("support_geom_ids"):
        return {**result, "unknown_reason": "missing_original_support_plane",
                "legacy_proxy_m": reference.get("lower_extent_m"),
                "legacy_proxy_source": reference.get("support_proxy_source", "legacy_settled_collision_lower_extent_proxy")}
    try:
        relative = np.asarray(sample["relative_com_tcp"], dtype=float)
        initial = np.asarray(initial_relative, dtype=float)
        if (relative.shape != (3,) or initial.shape != (3,)
                or not np.isfinite(relative).all() or not np.isfinite(initial).all()
                or not np.isfinite(float(plane))):
            raise ValueError
        displacement = float(np.linalg.norm(relative - initial))
        clearance = float(sample["lower_extent_m"]) - float(plane)
        dual = sample["dual_finger_contact"]
        if type(dual) is not bool or not np.isfinite(clearance):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return {**result, "unknown_reason": "missing_or_invalid_v3_tcp_com_lift_dual_finger_evidence"}
    result.update(clearance_m=clearance, dual_finger_contact=dual,
                  relative_com_tcp=relative.tolist(), relative_com_displacement_m=displacement,
                  original_support_plane_source=provenance["source"])
    # A known necessary predicate failure is false, even if counterfactual
    # evidence is missing. It cannot satisfy a lifted dual-finger hold.
    if clearance < V3_CLEARANCE_M or not dual or displacement > V3_RELATIVE_DISPLACEMENT_M:
        return {**result, "qualifies": False}
    evidence = sample.get("counterfactual_support_evidence") or {}
    load_bearing = sample.get("counterfactual_load_bearing_support")
    valid = (evidence.get("version") == "isolated-target-gripper-removal/1"
             and evidence.get("registration_id") == "grasp_truth_v3_1153_20261009"
             and evidence.get("status") == "known"
             and evidence.get("model_sha256") and evidence.get("integration_state_sha256")
             and evidence.get("native_collision_masks_preserved") is True
             and evidence.get("pair_coverage_complete") is True
             and evidence.get("target_gripper_contacts_after_removal") == 0
             and evidence.get("max_robot_drift_m", float("inf")) <= .001
             and evidence.get("max_robot_angle_drift_rad", float("inf")) <= .001
             and evidence.get("value") is load_bearing and type(load_bearing) is bool)
    if not valid:
        return {**result, "unknown_reason": "missing_registered_isolated_counterfactual_evidence"}
    return {**result, "counterfactual_load_bearing_support": load_bearing,
            "qualifies": not load_bearing}

def sustained_grasp_v3(samples: list[dict], reference: dict, duration_s: float = V3_DURATION_S) -> dict:
    """Registered v3 truth: lift, dual-finger contact and TCP-frame hold."""
    if not samples:
        raise ValueError("no physical hold samples")
    initial = samples[0].get("relative_com_tcp")
    checks = [_v3_sample_check(sample, reference, float(samples[0]["sim_time"]), initial)
              for sample in samples]
    unknown = [i for i, check in enumerate(checks) if check["qualifies"] is None]
    elapsed = float(samples[-1]["sim_time"]) - float(samples[0]["sim_time"])
    gaps = [float(b["sim_time"]) - float(a["sim_time"]) for a, b in zip(samples, samples[1:])]
    continuous = len(samples) >= V3_MIN_SAMPLES and elapsed + 1e-8 >= duration_s and all(0 < g <= V3_MAX_SAMPLE_GAP_S + 1e-8 for g in gaps)
    success = (False if any(check["qualifies"] is False for check in checks) else
               None if unknown or not continuous else True)
    return {"success": success, "status": "unknown" if success is None else "passed" if success else "failed",
            "duration_s": elapsed, "required_duration_s": duration_s,
            "required_clearance_m": V3_CLEARANCE_M,
            "required_relative_displacement_m": V3_RELATIVE_DISPLACEMENT_M,
            "required_samples": V3_MIN_SAMPLES, "samples": len(samples),
            "continuous_20hz": continuous, "sample_gaps_s": gaps,
            "unknown_sample_indices": unknown, "checks": checks,
            "support_rule": SUPPORT_RULE_V3,
            "reference": "fixed_original_support_plane_dual_finger_tcp_mass_weighted_com_hold",
            "source": "simulation_diagnostic_only"}

def grasp_trace_summary_v3(reference: dict, samples: list[dict], duration_s: float = V3_DURATION_S) -> dict:
    """Summarize first and final v3 windows without bridging unknown evidence."""
    if not samples:
        return {"source": "simulation_diagnostic_only", "support_rule": SUPPORT_RULE_V3,
                "true_sustained_grasp_during_skill": None, "true_sustained_grasp_at_end": None,
                "samples": []}
    first, uncertain = None, False
    for end in range(V3_MIN_SAMPLES, len(samples) + 1):
        window = samples[end - V3_MIN_SAMPLES:end]
        truth = sustained_grasp_v3(window, reference, duration_s)
        uncertain |= truth["success"] is None
        if truth["success"] is True and first is None:
            first = truth
    final = sustained_grasp_v3(samples[-V3_MIN_SAMPLES:], reference, duration_s) if len(samples) >= V3_MIN_SAMPLES else None
    return {"source": "simulation_diagnostic_only", "support_rule": SUPPORT_RULE_V3,
            "true_sustained_grasp_during_skill": (True if first else None if uncertain or len(samples) < V3_MIN_SAMPLES else False),
            "true_sustained_grasp_at_end": None if final is None else final["success"],
            "first_sustained_grasp": first, "final_hold_window": final, "samples": samples}


def _counterfactual_metadata(env, name: str) -> dict:
    import mujoco
    from robots.libero.v5_grasp_support_worker import descendants

    obj = env.objects_dict[name]
    model = env.sim.model._model
    target_body = int(env.obj_body_id[name])
    target_bodies = descendants(model, target_body)
    robot_root = env.robots[0].robot_model.root_body
    root_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, robot_root)
    if root_id < 0:
        raise ValueError("robot root body unavailable")
    robot_bodies = descendants(model, root_id)
    gripper = env.robots[0].gripper
    grippers = tuple(gripper.values()) if isinstance(gripper, dict) else (gripper,)
    gripper_bodies = set()
    gripper_roots = []
    for component in grippers:
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, component.root_body)
        if gid < 0:
            raise ValueError("complete gripper subtree unavailable")
        gripper_roots.append(gid)
        gripper_bodies.update(descendants(model, gid))
    target_joints = [j for j in range(model.njnt) if int(model.jnt_bodyid[j]) in target_bodies
                     and int(model.jnt_type[j]) == int(mujoco.mjtJoint.mjJNT_FREE)]
    if len(target_joints) != 1:
        raise ValueError("target free joint unavailable")
    robot_joints = [j for j in range(model.njnt) if int(model.jnt_bodyid[j]) in robot_bodies]
    qpos_ids, dof_ids = [], []
    for joint in robot_joints:
        kind = int(model.jnt_type[joint])
        nq, nv = (7, 6) if kind == 0 else (4, 3) if kind == 1 else (1, 1)
        qpos_ids.extend(range(int(model.jnt_qposadr[joint]), int(model.jnt_qposadr[joint]) + nq))
        dof_ids.extend(range(int(model.jnt_dofadr[joint]), int(model.jnt_dofadr[joint]) + nv))
    target_dof = int(model.jnt_dofadr[target_joints[0]])
    return {"state_spec": int(mujoco.mjtState.mjSTATE_INTEGRATION),
            "target_root_body_id": target_body, "robot_root_body_id": root_id,
            "gripper_root_body_ids": gripper_roots,
            "target_geom_ids": [i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in target_bodies],
            "gripper_geom_ids": [i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in gripper_bodies],
            "target_body_ids": target_bodies, "robot_body_ids": robot_bodies,
            "robot_qpos_ids": qpos_ids, "robot_dof_ids": dof_ids,
            "target_free_dof_ids": list(range(target_dof, target_dof + 6)),
            "complete_gripper_geometry": True,
            "unserialised_callback_present": mujoco.get_mjcb_contactfilter() is not None}


def _integration_state(env) -> np.ndarray:
    import mujoco

    model, data = env.sim.model._model, env.sim.data._data
    spec = int(mujoco.mjtState.mjSTATE_INTEGRATION)
    state = np.empty(mujoco.mj_stateSize(model, spec))
    mujoco.mj_getState(model, data, state, spec)
    return state


def _counterfactual_batch(env, name: str, states: list[np.ndarray]) -> list[dict]:
    import hashlib
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import tempfile
    import mujoco
    from robots.libero.v5_grasp_support_worker import unknown

    try:
        archive = Path(os.environ["LIBERO_GRASP_DIAGNOSTIC_MODELS"])
        if not archive.is_absolute():
            raise ValueError("model archive path must be absolute")
        archive.mkdir(parents=True, exist_ok=True)
        model = env.sim.model._model
        buffer = np.empty(mujoco.mj_sizeModel(model), dtype=np.uint8)
        mujoco.mj_saveModel(model, buffer=buffer)
        binary = buffer.tobytes()
        digest = hashlib.sha256(binary).hexdigest()
        model_path = archive / (digest + ".mjb")
        if not model_path.exists():
            with tempfile.NamedTemporaryFile(dir=archive, delete=False) as stream:
                stream.write(binary)
                temporary = stream.name
            os.replace(temporary, model_path)
        metadata = _counterfactual_metadata(env, name)
        with tempfile.TemporaryDirectory(prefix="private-grasp-support-") as tmp:
            tmp = Path(tmp)
            np.savez(tmp / "states.npz", states=np.asarray(states))
            packet = {"model_path": str(model_path), "model_sha256": digest,
                      "states_path": str(tmp / "states.npz"), "metadata": metadata,
                      "output_path": str(tmp / "results.json")}
            (tmp / "packet.json").write_text(json.dumps(packet))
            worker = Path(__file__).with_name("v5_grasp_support_worker.py")
            run = subprocess.run([sys.executable, str(worker), str(tmp / "packet.json")],
                                 capture_output=True, text=True, timeout=120)
            if run.returncode:
                raise RuntimeError(run.stderr[-2000:])
            results = json.loads((tmp / "results.json").read_text())
        return [{**r, "model_path": str(model_path), "metadata": metadata} for r in results]
    except Exception as exc:
        return [unknown("counterfactual_batch_failed:" + repr(exc)) for _ in states]

def enrich_registered_samples(env, name: str, reference: dict, samples: list[dict], states: list[np.ndarray]) -> None:
    """Run scoring only after controls stop; retain each complete snapshot."""
    if len(samples) != len(states):
        raise ValueError("contact/integration-state sample count differs")
    # Only lifted dual-finger frames need a support intervention. Known
    # necessary-predicate failures remain false without a counterfactual.
    plane = reference.get("original_support_plane_z_m")
    selected = [i for i, sample in enumerate(samples)
                if plane is not None and sample.get("dual_finger_contact") is True
                and sample.get("lower_extent_m", float("-inf")) - plane >= V3_CLEARANCE_M]
    results = _counterfactual_batch(env, name, [states[i] for i in selected]) if selected else []
    by_index = dict(zip(selected, results))
    for i, (sample, state) in enumerate(zip(samples, states)):
        sample["integration_state"] = state.tolist()
        sample["integration_state_spec"] = _counterfactual_metadata(env, name)["state_spec"]
        if i in by_index:
            evidence = by_index[i]
            sample["counterfactual_load_bearing_support"] = evidence["value"]
            sample["counterfactual_support_evidence"] = evidence


def measure_hold(wrapper, name: str, reference: dict, duration_s: float = .5) -> dict:
    """Measure a post-skill hold in the private original-task worker only."""
    if not 0 < duration_s <= 2:
        raise ValueError("registered grasp hold must be at most two seconds")
    env = wrapper.env
    samples = [contact_sample(env, name)]
    states = [_integration_state(env)]
    steps = 0
    while samples[-1]["sim_time"] - samples[0]["sim_time"] + 1e-8 < duration_s:
        action = np.zeros(7, dtype=np.float32)
        action[-1] = 1
        wrapper.step(action)
        steps += 1
        sample = contact_sample(env, name)
        samples.append(sample)
        states.append(_integration_state(env))
        if steps > 200:
            raise RuntimeError("physical hold clock did not advance")
    enrich_registered_samples(env, name, reference, samples, states)
    return {"reference": reference, "truth": sustained_grasp(samples, reference, duration_s),
            "truth_v2": sustained_grasp_v2(samples, reference, duration_s),
            "truth_v3": sustained_grasp_v3(samples, reference, duration_s),
            "samples": samples, "diagnostic_actions": steps,
            "policy_and_runtime_verifier_unchanged": True}
