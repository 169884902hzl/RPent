# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Development grasp verifier using independent measured views only.

No simulator queries, state rendering or runtime integration live here. Opening
calibration must come from original-task measurements. A wide opening alone is
neither success nor failure: fresh measured points near both fingers are needed.
"""

from dataclasses import asdict, is_dataclass
from itertools import product
import math

import numpy as np


VERSION = "measured-grasp-independent-views/1-dev"


def _record(entity):
    if entity is None:
        return None
    if is_dataclass(entity):
        return {**asdict(entity), "src": "perception"}
    return dict(entity)


def _current(entity, previous_step):
    return bool(entity and entity.get("visible") and entity.get("src", "").startswith("perception")
                and "cached" not in entity.get("src", "")
                and entity["source_step"] > previous_step)


def _finger_geometry(entity, eef_xyz, opening, finger_frame, tolerance):
    if finger_frame is None:
        # The prior public volume remains explicit. Wide-opening acceptance
        # below requires the calibrated pose frame and measured point cloud.
        near = bool(all(entity["lower"][i] - .04 <= eef_xyz[i] <= entity["upper"][i] + .04
                        for i in (0, 1))
                    and entity["lower"][2] - .03 <= eef_xyz[2] <= entity["upper"][2] + .15)
        return near, {"mode": "prior_world_axis_volume"}
    rotation = np.asarray(finger_frame["rotation_world_from_fingers"], dtype=float)
    origin = np.asarray(finger_frame["origin_world"], dtype=float)
    if (rotation.shape != (3, 3) or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6)
            or not np.isclose(np.linalg.det(rotation), 1.0, atol=1e-6)):
        raise ValueError("finger frame must use a proper proprioceptive rotation")
    corners = np.asarray(list(product(*zip(entity["lower"], entity["upper"]))))
    local = (corners - origin) @ rotation
    lower, upper = local.min(axis=0), local.max(axis=0)
    closing = finger_frame["closing_axis"]
    other = [i for i in range(3) if i != closing]
    half = np.zeros(3)
    half[closing] = opening / 2 + tolerance
    half[other[0]] = finger_frame["depth_half_m"]
    half[other[1]] = finger_frame["height_half_m"]
    near = bool(np.all(lower <= half) and np.all(upper >= -half))
    return near, {"mode": "calibrated_finger_frame", "object_lower_local_m": lower.tolist(),
                  "object_upper_local_m": upper.tolist(), "contact_volume_half_m": half.tolist(),
                  "provenance": finger_frame["provenance"]}


def _opening_check(opening, calibration, points, entity, finger_frame):
    evidence = {"opening_m": opening, "calibration": calibration}
    if calibration is None:
        return None, {**evidence, "reason": "original_opening_calibration_missing"}
    tolerance = calibration["tolerance_m"]
    if opening <= calibration["closed_empty_max_m"] + tolerance:
        return False, {**evidence, "reason": "matches_calibrated_empty_closed_range"}
    if opening > calibration["max_sensor_opening_m"] + tolerance:
        return None, {**evidence, "reason": "outside_original_calibration_range"}
    if opening < calibration["open_empty_min_m"] - tolerance:
        return True, {**evidence, "reason": "nonempty_opening_away_from_empty_open_range"}
    if finger_frame is None or points is None:
        return None, {**evidence, "reason": "wide_opening_needs_measured_finger_geometry"}
    if calibration.get("minimum_points_per_finger") is None:
        return None, {**evidence, "reason": "measured_finger_evidence_threshold_not_calibrated"}
    if (points.get("src") != "perception" or points.get("source_step") != entity["source_step"]
            or points.get("object_id") != entity["id"]):
        return None, {**evidence, "reason": "finger_geometry_points_not_current_perception"}
    world = np.asarray(points["xyz_world"], dtype=float)
    if world.ndim != 2 or world.shape[1:] != (3,) or not np.isfinite(world).all():
        raise ValueError("measured finger geometry needs finite Nx3 points")
    rotation = np.asarray(finger_frame["rotation_world_from_fingers"], dtype=float)
    local = (world - np.asarray(finger_frame["origin_world"])) @ rotation
    closing = finger_frame["closing_axis"]
    other = [i for i in range(3) if i != closing]
    inside = ((abs(local[:, other[0]]) <= finger_frame["depth_half_m"])
              & (abs(local[:, other[1]]) <= finger_frame["height_half_m"]))
    contact = local[inside, closing]
    counts = [int(np.count_nonzero(abs(contact - side * opening / 2) <= tolerance)) for side in (-1, 1)]
    enough = all(count >= calibration["minimum_points_per_finger"] for count in counts)
    width = float(np.ptp(contact)) if len(contact) else None
    return enough, {**evidence, "reason": "measured_both_finger_regions" if enough else "measured_finger_regions_not_both_supported",
                    "points_in_contact_volume": int(len(contact)), "points_per_finger": counts,
                    "measured_contact_width_m": width}


def evaluate_grasp_frame(before, views, opening, eef_xyz, *, previous_step,
                         opening_calibration=None, finger_frame=None,
                         measured_points_by_view=None, support_top_z_m=None,
                         require_support_clearance=False, minimum_lift_m=.03):
    """Return nullable verdict and every view's conditions without mutation.

    ``views`` is a camera->Entity/record mapping, saved separately by the caller.
    ``finger_frame`` uses proprioception plus calibrated rigid robot geometry;
    ``measured_points_by_view`` contains tagged fresh SAM RGB-D points.
    A pan requiring original-support clearance must supply its measured support
    top. Neither a cached object nor a missing support measurement proves lift.
    """
    before = _record(before)
    measured_points_by_view = measured_points_by_view or {}
    if not math.isfinite(opening) or not np.isfinite(eef_xyz).all():
        raise ValueError("nonfinite gripper proprioception")
    evidence = {}
    for camera, measured in views.items():
        entity = _record(measured)
        current = _current(entity, previous_step)
        frame = {"current_measurement": current, "measurement": entity,
                 "conditions": {"fresh_visible": True if current else None}}
        if not current:
            frame.update(verified=None, reason="current_visible_measurement_missing")
            evidence[camera] = frame
            continue
        if (before is None or not before.get("visible")
                or not before.get("src", "").startswith("perception")
                or "cached" in before.get("src", "")):
            frame.update(verified=None, reason="measured_pregrasp_baseline_missing")
            evidence[camera] = frame
            continue
        if entity["id"] != before["id"] or entity["name"] != before["name"]:
            frame.update(verified=None, reason="measured_entity_binding_changed")
            evidence[camera] = frame
            continue
        lift = entity["lower"][2] - before["lower"][2]
        tolerance = opening_calibration["tolerance_m"] if opening_calibration else .004
        near, geometry = _finger_geometry(entity, eef_xyz, opening, finger_frame, tolerance)
        nonempty, aperture = _opening_check(opening, opening_calibration,
                                            measured_points_by_view.get(camera), entity, finger_frame)
        clearance = (entity["lower"][2] - support_top_z_m) if support_top_z_m is not None else None
        support = (bool(clearance >= minimum_lift_m) if clearance is not None else None) if require_support_clearance else True
        conditions = {"fresh_visible": True, "measured_lower_lift": bool(lift >= minimum_lift_m),
                      "near_measured_fingers": near, "calibrated_nonempty_opening": nonempty,
                      "original_measured_support_clearance": support}
        values = list(conditions.values())
        verified = False if any(value is False for value in values) else None if None in values else True
        frame.update(conditions=conditions, verified=verified,
                     reason="measured_conditions_pass" if verified is True else "measured_condition_rejected" if verified is False else "required_measurement_or_calibration_missing",
                     lower_lift_m=lift, original_support_clearance_m=clearance,
                     finger_geometry=geometry, opening_evidence=aperture)
        evidence[camera] = frame
    known = {view["verified"] for view in evidence.values() if view["verified"] is not None}
    if len(known) > 1:
        verified, reason = None, "fresh_views_disagree"
    elif known:
        verified, reason = next(iter(known)), "independent_current_view_evidence"
    else:
        verified, reason = None, "current_evidence_insufficient"
    selected = next((camera for camera, view in evidence.items() if view["verified"] is verified), None) if verified is not None else None
    return {"version": VERSION, "verified": verified, "reason": reason, "selected_view": selected,
            "per_view": evidence, "eef_xyz": list(eef_xyz), "opening_m": opening,
            "previous_step": previous_step, "require_support_clearance": require_support_clearance}


def evaluate_grasp_pair(first, second, interval_s, *, minimum_interval_s=.3):
    """Require two independently current measured frames, with unknown preserved."""
    frames = [first, second]
    conditions = {"distinct_stable_interval": bool(interval_s >= minimum_interval_s),
                  "first_frame": first["verified"], "second_frame": second["verified"]}
    steps, identities = [], []
    for frame in frames:
        camera = frame.get("selected_view")
        steps.append(frame["per_view"][camera]["measurement"]["source_step"] if camera else None)
        identities.append(frame["per_view"][camera]["measurement"]["id"] if camera else None)
    conditions["distinct_capture_steps"] = bool(steps[1] > steps[0]) if None not in steps else None
    conditions["same_measured_entity"] = bool(identities[0] == identities[1]) if None not in identities else None
    values = list(conditions.values())
    verified = False if any(value is False for value in values) else None if None in values else True
    return {"version": VERSION, "verified": verified,
            "verification": "verified" if verified is True else "failed" if verified is False else "unmeasured",
            "conditions": conditions, "interval_s": interval_s, "frames": frames,
            "qualified_on_independent_original_confirmation": False}
