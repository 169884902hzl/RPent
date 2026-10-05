"""Private original-task grasp metrology, never a runtime decision input."""

from __future__ import annotations

import numpy as np


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
    grippers = gripper.values() if isinstance(gripper, dict) else (gripper,)
    fingers = {geom for component in grippers
               for key, geoms in component.important_geoms.items()
               if "finger" in key for geom in geoms}
    touching, finger_contacts, other_contacts = [], [], []
    for index in range(data.ncon):
        contact = data.contact[index]
        a = model.geom_id2name(int(contact.geom1)) or f"unnamed_geom:{int(contact.geom1)}"
        b = model.geom_id2name(int(contact.geom2)) or f"unnamed_geom:{int(contact.geom2)}"
        if (a in target) == (b in target):
            continue
        other = b if a in target else a
        touching.append({"geom1": a, "geom2": b, "distance_m": float(contact.dist)})
        (finger_contacts if other in fingers else other_contacts).append(other)
    return {"sim_time": float(data.time), "target": name,
            "lower_extent_m": object_lower_extent(env, obj),
            "finger_contact": bool(finger_contacts),
            "dual_finger_contact": bool(env._check_grasp(gripper, obj.contact_geoms)),
            "finger_geoms": sorted(set(finger_contacts)),
            "other_contact_geoms": sorted(set(other_contacts)), "contacts": touching}


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
