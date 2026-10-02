# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Furniture surfaces derived from the visible parent's RGB-D point cloud."""

import numpy as np

from robots.libero.v5_state import Entity


def fixture_points(world, parent: Entity):
    """Select measured RGB-D points inside the segmented parent's bounds."""
    cloud = np.asarray(world).reshape(-1, 3)
    keep = np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)
    keep &= ((cloud >= np.asarray(parent.lower) - .002)
             & (cloud <= np.asarray(parent.upper) + .002)).all(axis=1)
    return cloud[keep]


def above_work_surface(parent: Entity, support_z: float | None) -> bool:
    """Reject a tabletop fixture detection wholly below measured object support."""
    return support_z is None or parent.upper[2] >= support_z - .02


def fixture_parts(parent: Entity, points, front_axis) -> list[dict]:
    """Return measured bands, leaving an occluded/empty band absent.

    Drawer names denote geometric bands of a cabinet front. This does not
    assert that an occluded interior or a movable handle has been measured.
    """
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    if len(points) < 30:
        return []
    zlo, zhi = np.quantile(points[:, 2], (.02, .98))
    if parent.name == "cabinet" and zhi - zlo <= .03:
        return []
    front = np.asarray(front_axis)
    projection = points @ front
    face = points[projection >= np.quantile(projection, .65)]
    groups = []
    if parent.name == "cabinet":
        edges = np.linspace(zlo, zhi, 4)
        for index, label in enumerate(("bottom", "middle", "top")):
            band = face[(face[:, 2] >= edges[index]) & (face[:, 2] <= edges[index + 1])]
            groups.append((f"cabinet {label} drawer", band, "measured_front_band"))
        groups.append(("cabinet top surface", points[points[:, 2] >= zhi - .01], "measured_top_surface"))
    elif parent.name == "microwave":
        groups.append(("microwave door", face, "measured_front_surface"))
    elif parent.name == "stove":
        groups.append(("stove top surface", points[points[:, 2] >= zhi - .01], "measured_top_surface"))
    result = []
    for name, cloud, geometry in groups:
        if len(cloud) < 10:
            continue
        lower, upper = np.quantile(cloud, (.02, .98), axis=0)
        result.append({"name": name, "xyz": tuple(np.median(cloud, axis=0)),
                       "lower": tuple(lower), "upper": tuple(upper), "geometry": geometry})
    return result
