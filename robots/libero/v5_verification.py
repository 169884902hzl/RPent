# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Placement and articulation checks using saved RGB-D measurements only."""

import math

import numpy as np

from robots.libero.v5_state import Entity, place_verified


def placement_verification_status(
    verified: bool | None, first: Entity | None, second: Entity | None
) -> str:
    """Classify placement evidence identically online and during re-rendering.

    A missing or occluded frame cannot establish a physical placement failure.
    Motion and precondition failures are handled before this visual check.
    """
    if verified is None:
        return "unverified"
    if verified:
        return "verified"
    if first is None or second is None or not (first.visible and second.visible):
        return "unverified"
    return "failed"


def strict_place_verified(first, second, target, opening, eef_xyz, interval_s, *, relation="on", minimum_footprint_overlap=.85):
    """Require stable release plus footprint support or measured containment.

    Thresholds are development parameters. Precision must be measured against
    original-task physical predicates before this check is retained.
    """
    if not place_verified(first, second, target, opening, eef_xyz, interval_s,
                          relation=relation):
        return False
    for measured in (first, second):
        area = math.prod(max(measured.upper[i] - measured.lower[i], 1e-6) for i in (0, 1))
        overlap = math.prod(max(0.0, min(measured.upper[i], target.upper[i])
                                - max(measured.lower[i], target.lower[i])) for i in (0, 1))
        if overlap / area < minimum_footprint_overlap:
            return False
        if relation == "on" and abs(measured.lower[2] - target.upper[2]) > 0.02:
            return False
        if relation == "in" and measured.lower[2] < target.lower[2] - 0.01:
            return False
    return True


def strict_place_verified_v2(first, second, target, opening, eef_xyz, interval_s, *, relation="on"):
    """Original-task calibrated footprint support; containment is unchanged."""
    return strict_place_verified(first, second, target, opening, eef_xyz, interval_s,
                                 relation=relation,
                                 minimum_footprint_overlap=.90 if relation == "on" else .85)


def strict_place_verified_v3(first, second, target, opening, eef_xyz, interval_s, *, relation="on"):
    """A fixture's visible door or shell cannot verify interior containment."""
    if relation == "in" and (
            "microwave" in target.name
            or target.geometry in ("measured_front_surface", "measured_door_surface")):
        if target.geometry != "measured_cavity":
            return None
    return strict_place_verified_v2(first, second, target, opening, eef_xyz, interval_s,
                                    relation=relation)


def strict_place_verified_v4(first, second, target, opening, eef_xyz, interval_s, *, relation="on"):
    """An instruction's table region is a destination, not a support object.

    Keep centre membership, measured contact, two-frame stability and released
    withdrawal. Footprint support still applies to physical destination objects.
    """
    if relation == "on" and target.name.startswith("area "):
        if not place_verified(first, second, target, opening, eef_xyz, interval_s, relation=relation):
            return False
        return all(abs(measured.lower[2] - target.upper[2]) <= .02 for measured in (first, second))
    return strict_place_verified_v3(first, second, target, opening, eef_xyz, interval_s, relation=relation)


def measured_articulation(before: Entity, after: Entity | None, mode: str,
                          front_axis) -> tuple[bool | None, dict]:
    """Verify an observed drawer displacement; absent/door evidence is unknown."""
    if after is None or not after.visible or before.source_step == after.source_step:
        return None, {"reason": "no_distinct_after_measurement"}
    if front_axis is None:
        return None, {"reason": "fixture_motion_axis_not_measured"}
    displacement = sum((after.xyz[i] - before.xyz[i]) * front_axis[i] for i in (0, 1))
    evidence = {"measured_front_displacement_cm": round(displacement * 100, 2),
                "before_step": before.source_step, "after_step": after.source_step}
    if "drawer" in before.name and mode in ("open", "close"):
        # This establishes measured movement, not a fully open/closed endpoint.
        correct = bool(displacement >= 0.02 if mode == "open" else displacement <= -0.02)
        return correct, {**evidence, "verification_scope": "requested_drawer_motion"}
    return None, {**evidence, "reason": "door_endpoint_geometry_not_calibrated"}


def vertical_face(points):
    """Fit a visible vertical face; reject curved or poorly supported clouds."""
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 30 or np.ptp(points[:, 2]) < .04:
        return None
    centre = np.median(points, axis=0)
    values, vectors = np.linalg.eigh(np.cov(points[:, :2].T))
    normal = vectors[:, 0]
    residual = np.abs((points[:, :2] - centre[:2]) @ normal)
    if np.sqrt(max(values[1], 0)) < .015 or np.quantile(residual, .9) > .008:
        return None
    return {"centre": centre.tolist(), "normal_xy": normal.tolist(),
            "residual_p90_m": float(np.quantile(residual, .9)), "points": len(points)}


def moving_panel_points(points, fixed_anchor):
    """Remove an observed static frame and fit the dominant moving panel.

    A SAM door mask can include its handle and the fixed appliance front.
    The reference patch must have been independently measured while the door
    was open. Keep the existing plane residual and extent checks; an ambiguous
    or weakly supported plane stays unknown.
    """
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    evidence = {"basis": "measured_static_patch_exclusion_and_panel_consensus/1-dev",
                "input_points": len(points)}
    if fixed_anchor is None:
        return points, {**evidence, "reason": "no_independent_fixed_patch"}
    lo, hi = np.asarray(fixed_anchor["lower"]), np.asarray(fixed_anchor["upper"])
    static = ((points[:, :2] >= lo[:2] - .01)
              & (points[:, :2] <= hi[:2] + .01)).all(axis=1)
    points = points[~static]
    evidence.update(fixed_patch_excluded=int(static.sum()),
                    fixed_patch_source_step=fixed_anchor["source_step"])
    if np.mean(static) >= .5:
        return points[:0], {**evidence, "reason": "mask_is_mostly_the_fixed_reference"}
    if len(points) < 60:
        return points[:0], {**evidence, "reason": "moving_panel_not_measured"}
    # Use two horizontally separated measured points for a vertical plane.
    rng = np.random.default_rng(0)
    sample = points[rng.choice(len(points), min(len(points), 2500), replace=False)]
    pairs = rng.choice(len(sample), (128, 2), replace=True)
    vectors = sample[pairs[:, 1], :2] - sample[pairs[:, 0], :2]
    norms = np.linalg.norm(vectors, axis=1)
    supported = norms > .05
    if not np.any(supported):
        return points[:0], {**evidence, "reason": "moving_panel_width_not_measured"}
    normals = np.stack([-vectors[supported, 1], vectors[supported, 0]], axis=1) / norms[supported, None]
    anchors = sample[pairs[supported, 0], :2]
    distances = np.abs(np.einsum("nmi,mi->nm", sample[:, None, :2] - anchors, normals))
    best = int(np.argmax(np.sum(distances <= .004, axis=0)))
    inliers = np.abs((points[:, :2] - anchors[best]) @ normals[best]) <= .004
    fraction = float(np.mean(inliers))
    panel = points[inliers]
    evidence.update(remaining_points=len(points), panel_points=len(panel),
                    panel_fraction=fraction, inlier_distance_m=.004)
    if fraction < .55 or vertical_face(panel) is None:
        return points[:0], {**evidence, "reason": "dominant_vertical_panel_not_measured"}
    return panel, evidence


def measured_fixture_endpoint(before, after, mode, *, drawer):
    """Compare the moving measured face against a stable measured frame."""
    evidence = {"verification_scope": "measured_fixture_endpoint/2-dev",
                "before": before, "after": after}
    if mode not in ("open", "close") or not all(
            sample and sample.get("frame") and sample.get("moving") for sample in (before, after)):
        return None, {**evidence, "reason": "moving_face_or_static_frame_not_measured"}
    if before["source_step"] == after["source_step"]:
        return None, {**evidence, "reason": "no_distinct_after_measurement"}
    old, frame = before["frame"], after["frame"]
    normal = np.asarray(frame["normal_xy"])
    angle = math.degrees(math.acos(float(np.clip(abs(normal @ np.asarray(old["normal_xy"])), 0, 1))))
    drift = abs((np.asarray(frame["centre"][:2]) - old["centre"][:2]) @ normal)
    if angle > 10 or drift > .01:
        return None, {**evidence, "reason": "reference_frame_not_stable"}
    face = after["moving"]
    if drawer:
        distance = abs((np.asarray(face["centre"][:2]) - frame["centre"][:2]) @ normal)
        evidence["measured_extension_cm"] = round(float(distance) * 100, 2)
        return bool(distance >= .025 if mode == "open" else distance <= .015), evidence
    angle = math.degrees(math.acos(float(np.clip(abs(normal @ np.asarray(face["normal_xy"])), 0, 1))))
    evidence["measured_door_angle_deg"] = round(angle, 2)
    return bool(angle >= 30 if mode == "open" else angle <= 15), evidence
