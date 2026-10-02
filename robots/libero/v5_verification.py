# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Placement and articulation checks using saved RGB-D measurements only."""

import math

from robots.libero.v5_state import Entity, place_verified


def strict_place_verified(first, second, target, opening, eef_xyz, interval_s, *, relation="on"):
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
        if overlap / area < 0.85:
            return False
        if relation == "on" and abs(measured.lower[2] - target.upper[2]) > 0.02:
            return False
        if relation == "in" and measured.lower[2] < target.lower[2] - 0.01:
            return False
    return True


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
