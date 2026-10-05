"""Private original-task grasp metrology, never a runtime decision input."""

from __future__ import annotations

import numpy as np


GRIPPER_GEOMETRY_VERSION = "gripper_geometry/1"
GRIPPER_GEOMETRY_SOURCE = "component.contact_geoms+component.important_geoms"
SUPPORT_RULE_V2 = "all_current_non_gripper_contacts/2"


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
    for index in range(data.ncon):
        contact = data.contact[index]
        a = model.geom_id2name(int(contact.geom1)) or f"unnamed_geom:{int(contact.geom1)}"
        b = model.geom_id2name(int(contact.geom2)) or f"unnamed_geom:{int(contact.geom2)}"
        if (a in target) == (b in target):
            continue
        other = b if a in target else a
        touching.append({"geom1": a, "geom2": b, "distance_m": float(contact.dist)})
        (finger_contacts if other in fingers else other_contacts).append(other)
        if other not in gripper_geoms:
            non_gripper_contacts.append(other)
    return {"sim_time": float(data.time), "target": name,
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


def measure_hold(wrapper, name: str, reference: dict, duration_s: float = .5) -> dict:
    """Measure a post-skill hold in the private original-task worker only."""
    if not 0 < duration_s <= 2:
        raise ValueError("registered grasp hold must be at most two seconds")
    env = wrapper.env
    samples = [contact_sample(env, name)]
    steps = 0
    while samples[-1]["sim_time"] - samples[0]["sim_time"] + 1e-8 < duration_s:
        action = np.zeros(7, dtype=np.float32)
        action[-1] = 1
        wrapper.step(action)
        steps += 1
        samples.append(contact_sample(env, name))
        if steps > 200:
            raise RuntimeError("physical hold clock did not advance")
    return {"truth": sustained_grasp(samples, reference, duration_s), "samples": samples,
            "diagnostic_actions": steps, "policy_and_runtime_verifier_unchanged": True}
