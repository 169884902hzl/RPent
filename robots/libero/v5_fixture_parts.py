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


def associated_drawers(parent: Entity, cabinets: list[Entity], drawers: list[Entity]) -> list[Entity]:
    """Bind a separately segmented drawer only to one nearby measured cabinet.

    An open drawer need not lie inside its cabinet's segmentation bounds.
    Ambiguous cabinet associations remain absent rather than using task goals.
    """
    result = []
    for drawer in drawers:
        matches = []
        for cabinet in cabinets:
            if not cabinet.visible:
                continue
            if not cabinet.lower[2] - .02 <= drawer.xyz[2] <= cabinet.upper[2] + .02:
                continue
            gap = np.maximum(0, np.maximum(
                np.asarray(cabinet.lower[:2]) - drawer.upper[:2],
                np.asarray(drawer.lower[:2]) - cabinet.upper[:2]))
            if np.linalg.norm(gap) <= .25:
                matches.append(cabinet.id)
        if matches == [parent.id]:
            result.append(drawer)
    return result


def infer_cabinet_front(points, camera_xyz, previous_axis=None):
    """Calibrate a visible protruding drawer face from measured depth bands.

    A camera's image-forward axis is not a fixture's opening axis. Keep a
    previously measured fixture axis when its drawers close. Without a
    distinct visible depth profile, leave the drawer-front direction unknown.
    """
    if previous_axis is not None:
        return tuple(previous_axis), {"basis": "previous_measured_drawer_profile"}
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 60 or camera_xyz is None:
        return None, {"reason": "insufficient_depth_or_camera_calibration"}
    zlo, zhi = np.quantile(points[:, 2], (.02, .98))
    if zhi - zlo <= .03:
        return None, {"reason": "insufficient_cabinet_height"}
    edges = np.linspace(zlo, zhi, 4)
    bands = [points[(points[:,2] >= edges[i]) & (points[:,2] <= edges[i+1])] for i in range(3)]
    if any(len(band) < 20 for band in bands):
        return None, {"reason": "missing_visible_height_band"}
    towards_camera = np.asarray(camera_xyz)[:2] - np.median(points[:, :2], axis=0)
    profiles = []
    for axis in ((1.,0.,0.),(-1.,0.,0.),(0.,1.,0.),(0.,-1.,0.)):
        # Reject the back-facing sides; their missing pixels can masquerade as
        # a large depth change between height bands.
        if np.dot(np.asarray(axis)[:2], towards_camera) <= .02:
            continue
        profile = [float(np.quantile(band @ np.asarray(axis), .9)) for band in bands]
        profiles.append({"axis": axis, "edge_profile_m": profile,
                         "profile_range_m": max(profile) - min(profile)})
    profiles.sort(key=lambda item:item["profile_range_m"], reverse=True)
    evidence = {"basis": "visible_rgbd_height_band_depth_profile", "profiles": profiles}
    if not profiles or profiles[0]["profile_range_m"] < .025:
        return None, {**evidence, "reason": "no_measured_drawer_protrusion"}
    if len(profiles) > 1 and profiles[0]["profile_range_m"] - profiles[1]["profile_range_m"] < .01:
        return None, {**evidence, "reason": "ambiguous_fixture_front"}
    return profiles[0]["axis"], evidence


def fixture_parts(parent: Entity, points, front_axis, *, calibrated_front=False) -> list[dict]:
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
    front = np.asarray(front_axis) if front_axis is not None else None
    face = points[points @ front >= np.quantile(points @ front, .65)] if front is not None else points[:0]
    groups = []
    if parent.name == "cabinet":
        edges = np.linspace(zlo, zhi, 4)
        for index, label in enumerate(("bottom", "middle", "top")):
            band = points[(points[:,2] >= edges[index]) & (points[:,2] <= edges[index+1])] if calibrated_front else face[(face[:, 2] >= edges[index]) & (face[:, 2] <= edges[index + 1])]
            if calibrated_front:
                band = band[band @ front >= np.quantile(band @ front, .65)] if front is not None and len(band) else points[:0]
            groups.append((f"cabinet {label} drawer", band, "measured_front_band"))
        groups.append(("cabinet top surface", points[points[:, 2] >= zhi - .01], "measured_top_surface"))
    elif parent.name == "microwave":
        groups.append(("microwave door", points if calibrated_front else face, "measured_door_surface" if calibrated_front else "measured_front_surface"))
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
