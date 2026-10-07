# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Current public shell-front geometry supplies a SAM hint, never a door label."""

import math

import numpy as np

from robots.libero.v5_microwave_door_temporal import MicrowaveDoorTemporalConfig
from robots.libero.v5_verification import vertical_face


VERSION = "microwave-current-public-shell-front-SAM-hint/1-dev"


def shell_front_panel_prompt(world, parent, fixed_anchor, *, source_step):
    """Prompt a front panel inside the shell when the external-panel hint misses.

    The fixed patch is independently measured while the door is open. Its
    bounds locate a current reference fit; no cached plane or inferred mask
    may become a door verdict. The caller must query SAM and retain the normal
    independent-mask, plane-consensus and temporal verification path.
    """
    from scipy.ndimage import distance_transform_edt, label

    config = MicrowaveDoorTemporalConfig()
    evidence = {"basis": VERSION, "source": "perception", "source_step": source_step,
                "trigger_only": True, "door_label_admitted": False, "stop_admitted": False,
                "panels": []}
    if (parent.name != "microwave" or not parent.visible or fixed_anchor is None
            or fixed_anchor.get("parent") != parent.id
            or type(fixed_anchor.get("source_step")) is not int
            or not 0 <= fixed_anchor["source_step"] <= source_step):
        return None, {**evidence, "reason": "independent_measured_shell_patch_missing"}
    world = np.asarray(world, dtype=float)
    if world.ndim != 3 or world.shape[-1] != 3:
        return None, {**evidence, "reason": "current_world_depth_invalid"}
    lo, hi = np.asarray(parent.lower), np.asarray(parent.upper)
    fixed_lo, fixed_hi = np.asarray(fixed_anchor["lower"]), np.asarray(fixed_anchor["upper"])
    valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    fixed = valid & ((world >= fixed_lo - .002) & (world <= fixed_hi + .002)).all(axis=-1)
    reference = vertical_face(world[fixed])
    if reference is None:
        return None, {**evidence, "reason": "current_fixed_front_patch_not_measured"}
    # Match existing fixed-patch selection and panel exclusion distances.
    normal = np.asarray(reference["normal_xy"])
    reference_distance = np.abs((world[..., :2] - reference["centre"][:2]) @ normal)
    static = ((world[..., :2] >= fixed_lo[:2] - .01)
              & (world[..., :2] <= fixed_hi[:2] + .01)).all(axis=-1)
    available = valid & ~static & (reference_distance <= config.maximum_plane_residual_m)
    available &= ((world >= lo - .015) & (world <= hi + .015)).all(axis=-1)
    available &= (world[..., 2] >= lo[2] + .01) & (world[..., 2] <= hi[2] - .01)
    evidence.update(current_fixed_reference=reference, fixed_patch_source_step=fixed_anchor["source_step"],
                    fixed_patch_pixels=int(fixed.sum()), candidate_pixels=int(available.sum()),
                    maximum_front_plane_distance_m=config.maximum_plane_residual_m)
    components, count = label(available)
    accepted = []
    for component in range(1, count + 1):
        mask = components == component
        if np.count_nonzero(mask) < 60:
            continue
        points = world[mask]
        fit = vertical_face(points)
        if fit is None:
            continue
        lower, upper = np.quantile(points, (.02, .98), axis=0)
        height = float(upper[2] - lower[2])
        angle = math.degrees(math.acos(float(np.clip(abs(normal @ fit["normal_xy"]), 0., 1.))))
        if height < .65 * (hi[2] - lo[2]) or angle > config.maximum_reference_angle_deg:
            continue
        accepted.append(mask)
        evidence["panels"].append({"plane": fit, "pixels": int(mask.sum()),
                                   "measured_height_m": height, "reference_angle_deg": angle})
    if len(accepted) != 1:
        return None, {**evidence, "reason": "current_shell_front_panel_missing_or_ambiguous"}
    point = list(map(int, np.unravel_index(np.argmax(distance_transform_edt(accepted[0])), available.shape)))
    return point, {**evidence, "point": point, "reason": "current_shell_front_point_for_SAM_only"}
