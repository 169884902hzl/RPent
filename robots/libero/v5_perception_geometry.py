# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Geometry estimated from calibrated, segmented RGB-D measurements only."""

from __future__ import annotations

import numpy as np


def measured_work_surface(world, object_bounds):
    """Find a connected depth plane adjacent to measured object footprints."""
    from scipy.ndimage import label

    if not object_bounds:
        return None
    world = np.asarray(world, dtype=float)
    valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
    height_hint = float(np.median([item.lower[2] for item in object_bounds]))
    bins = np.arange(height_hint - .04, height_hint + .014, .002)
    histogram, edges = np.histogram(world[..., 2][valid], bins=bins)
    if not np.any(histogram):
        return None
    index = int(np.argmax(histogram))
    height = float((edges[index] + edges[index + 1]) / 2)
    components, _ = label(valid & (np.abs(world[..., 2] - height) <= .003))
    sizes = np.bincount(components.ravel())
    choices = []
    for component in np.flatnonzero(sizes >= 200):
        if component == 0:
            continue
        points = world[components == component]
        sampled = points[::max(1, len(points) // 3000), :2]
        near = sum(float(np.min(np.linalg.norm(sampled - np.asarray(item.xyz[:2]), axis=1))) <= .12
                   for item in object_bounds)
        if near == 0:
            continue
        lower, upper = np.quantile(points, (.02, .98), axis=0)
        if min(upper[:2] - lower[:2]) < .1:
            continue
        choices.append((near, len(points), lower, upper))
    if not choices:
        return None
    choices.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if len(choices) > 1 and choices[0][0] == choices[1][0] and choices[1][1] >= .8 * choices[0][1]:
        return None
    near, count, lower, upper = choices[0]
    return {"basis": "current_rgbd_connected_support_plane/3-dev", "lower": lower.tolist(),
            "upper": upper.tolist(), "height_m": height, "points": count, "near_object_count": near}


def microwave_geometry_supported(lower, upper, surface, *, require_support_contact=False):
    """Reject an isolated door, robot-sized mask or a distant background box."""
    lower, upper = np.asarray(lower), np.asarray(upper)
    size = upper - lower
    if min(size[:2]) < .06 or max(size) > .6 or size[2] < .07:
        return False
    if surface is not None:
        lo, hi = np.asarray(surface["lower"]), np.asarray(surface["upper"])
        if np.any(upper[:2] < lo[:2] - .06) or np.any(lower[:2] > hi[:2] + .06):
            return False
        if upper[2] < surface["height_m"] - .01:
            return False
        if require_support_contact and lower[2] > surface["height_m"] + .08:
            return False
    return True


def fixture_overlaps_work_surface(lower, upper, surface, *, margin=.08):
    """Keep a fixture only when its measured footprint meets the work surface.

    A distant background cabinet can be taller than the table and therefore
    pass a height-only foreground filter.  The connected support plane gives
    the public RGB-D evidence needed to reject that unrelated detection.
    """
    if surface is None:
        return True
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    surface_lower = np.asarray(surface["lower"], dtype=float)
    surface_upper = np.asarray(surface["upper"], dtype=float)
    return bool(
        np.all(upper[:2] >= surface_lower[:2] - margin)
        and np.all(lower[:2] <= surface_upper[:2] + margin)
    )


def appliance_foreground_mask(world, mask, surface, *, crop_to_support=False):
    """Remove a measured tabletop from a compound appliance/door mask."""
    world = np.asarray(world, dtype=float)
    mask = np.asarray(mask, dtype=bool).copy()
    mask &= np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
    original = int(mask.sum())
    if surface is not None:
        # A thin door plus a large table patch otherwise looks like a volume.
        # This cutoff is relative to this capture's measured support plane.
        mask &= world[..., 2] > surface["height_m"] + .015
        if crop_to_support:
            mask &= np.all(world[..., :2] >= np.asarray(surface["lower"][:2]) - .06, axis=2)
            mask &= np.all(world[..., :2] <= np.asarray(surface["upper"][:2]) + .06, axis=2)
    return mask, {"basis": "current_rgbd_support_footprint_and_height/5-dev" if crop_to_support
                  else "current_rgbd_above_measured_support/4-dev",
                  "input_points": original, "retained_points": int(mask.sum()),
                  "support_available": surface is not None}


def same_segmented_instance(first_mask, second_mask):
    """Recognize nested masks of the same surface across text queries."""
    smaller = min(np.count_nonzero(first_mask), np.count_nonzero(second_mask))
    return bool(smaller and np.count_nonzero(first_mask & second_mask) / smaller > .85)


def measured_prompt_pixel(world, lower, upper):
    """Choose a current-depth surface pixel, excluding a small top protrusion."""
    from scipy.ndimage import distance_transform_edt

    lower, upper = np.asarray(lower), np.asarray(upper)
    valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
    support = valid & np.all(world >= lower - .01, axis=2) & np.all(world <= upper + .01, axis=2)
    support &= world[..., 2] >= lower[2] + .35 * (upper[2] - lower[2])
    # A point on the highest protrusion can segment only a knob or bottle cap.
    # Use the observed body surface below the prior measured upper bound.
    support &= world[..., 2] <= upper[2] - .002
    if np.count_nonzero(support) < 30:
        return None
    distance = distance_transform_edt(support)
    return list(map(int, np.unravel_index(np.argmax(distance), support.shape)))


def refinement_mask_matches(points, lower, upper):
    """Reject a distant mask or a small part of the previously observed object."""
    if len(points) < 30:
        return False
    lo, hi = np.quantile(points, (.02, .98), axis=0)
    lower, upper = np.asarray(lower), np.asarray(upper)
    centre = np.median(points, axis=0)
    return bool(np.all(centre >= lower - .02) and np.all(centre <= upper + .02)
                and np.all(hi[:2] - lo[:2] >= .3 * (upper[:2] - lower[:2]))
                and np.all(hi - lo <= (upper - lower) + .04))


def measured_rim_point(points, eef_xyz):
    """Stage over a visible upper rim, rather than an offset of partial bounds."""
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 30:
        return None
    top = np.quantile(points[:, 2], .95)
    rim = points[(points[:, 2] >= top - .008) & (points[:, 2] <= top + .005)]
    if len(rim) < 10:
        return None
    distance = np.linalg.norm(rim[:, :2] - np.asarray(eef_xyz)[:2], axis=1)
    anchor = rim[np.argmin(distance)]
    patch = rim[np.linalg.norm(rim[:, :2] - anchor[:2], axis=1) <= .01]
    return np.median(patch, axis=0) if len(patch) >= 3 else None


def measured_points(world, mask):
    """Drop missing depths; camera-to-world conversion belongs to capture."""
    points = np.asarray(world)[mask].astype(float)
    return points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]


def fuse_cloud(primary, secondary, *, max_gap=.08, trim_depth_tails=False):
    """Join one uniquely associated instance, retaining both views' points.

    Ambiguous same-category associations remain unfused. An occluded surface
    can be farther from the other view's median than the two objects' surfaces.
    Compare trimmed bounds as well as their measured centres.
    """
    primary = np.asarray(primary)
    lower, upper = np.quantile(primary, (.02, .98), axis=0)
    matches = []
    for index, (points, score) in enumerate(secondary):
        if len(points) < 10:
            continue
        lo, hi = np.quantile(points, (.02, .98), axis=0)
        gap = np.maximum(0, np.maximum(lower - hi, lo - upper))
        if np.linalg.norm(gap) <= .02 and np.linalg.norm((lo + hi - lower - upper) / 2) <= max_gap:
            matches.append((index, points, score))
    if len(matches) != 1:
        return primary, None, {"fused": False, "matching_views": len(matches)}
    index, points, score = matches[0]
    original_counts = len(primary), len(points)
    if trim_depth_tails:
        # Sparse depth outliers are negligible before voxelization, but each
        # distant voxel then weighs as much as a dense object-surface voxel.
        # Keep each camera's already measured robust bounds before equalizing
        # density; do not expand those bounds with amplified background tails.
        lo, hi = np.quantile(points, (.02, .98), axis=0)
        trimmed_primary = primary[np.all((primary >= lower) & (primary <= upper), axis=1)]
        trimmed_secondary = points[np.all((points >= lo) & (points <= hi), axis=1)]
        if min(len(trimmed_primary), len(trimmed_secondary)) < 10:
            return primary, None, {
                "fused": False, "matching_views": 1, "reason": "insufficient_trimmed_depth_support"}
        primary, points = trimmed_primary, trimmed_secondary
    # Equal spatial resolution keeps a dense close-up from erasing the main
    # camera's surface. Voxel centroids still contain measured points only.
    cloud = np.concatenate((primary, points))
    bins = np.floor(cloud / .002).astype(np.int64)
    _, inverse = np.unique(bins, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    cloud = np.column_stack([np.bincount(inverse, weights=cloud[:, i]) / counts for i in range(3)])
    evidence = {"fused": True, "matching_views": 1,
                          "primary_points": len(primary), "secondary_points": len(points),
                          "voxel_points": len(cloud), "secondary_score": score}
    if trim_depth_tails:
        evidence.update(depth_filter="per_view_quantile_before_voxelization/2",
                        raw_primary_points=original_counts[0], raw_secondary_points=original_counts[1])
    return cloud, index, evidence


def fit_shape(points, name):
    """Fit a vertical cylinder or an oriented box; refuse unsupported fits.

    These are surface-based estimates, not completed simulator geometry.
    Height remains bounded by observed depth. A cylinder can recover its
    horizontal centre from a curved side, whereas a single flat box face
    provides no evidence for unseen thickness.
    """
    points = np.asarray(points, dtype=float)
    lower, upper = np.quantile(points, (.02, .98), axis=0)
    centre = np.median(points, axis=0)
    evidence = {"basis": "segmented_rgbd_world_points", "shape": "visible_surface",
                "point_count": len(points), "accepted": False}
    if len(points) < 30:
        return centre, lower, upper, evidence
    cylindrical = any(word in name for word in ("bowl", "mug", "bottle", "soup", "tomato sauce", "ramekin"))
    if cylindrical:
        xy = points[:, :2]
        origin = np.median(xy, axis=0)
        xy = xy - origin
        matrix = np.column_stack((2 * xy, np.ones(len(xy))))
        estimate, _, rank, singular = np.linalg.lstsq(matrix, (xy * xy).sum(axis=1), rcond=None)
        radius2 = estimate[2] + (estimate[:2] ** 2).sum()
        if rank != 3 or radius2 <= 0 or singular[-1] <= 1e-9:
            return centre, lower, upper, {**evidence, "reason": "degenerate_cylinder"}
        radius = float(np.sqrt(radius2))
        fitted = origin + estimate[:2]
        residual = np.abs(np.linalg.norm(points[:, :2] - fitted, axis=1) - radius)
        error = float(np.quantile(residual, .75))
        evidence.update(shape="cylinder", radius_m=radius, residual_p75_m=error)
        if not .008 <= radius <= .12 or error > .012 or np.linalg.norm(fitted - centre[:2]) > radius:
            return centre, lower, upper, {**evidence, "reason": "unsupported_cylinder_fit"}
        centre[:2] = fitted
        centre[2] = (lower[2] + upper[2]) / 2
        lower[:2] = np.minimum(lower[:2], fitted - radius)
        upper[:2] = np.maximum(upper[:2], fitted + radius)
        return centre, lower, upper, {**evidence, "accepted": True}
    if any(word in name for word in ("box", "cheese", "butter", "pudding", "book", "milk")):
        xy = points[:, :2] - centre[:2]
        _, axes = np.linalg.eigh(np.cov(xy.T))
        local = xy @ axes
        lo, hi = np.quantile(local, (.02, .98), axis=0)
        if np.min(hi - lo) < .008:
            return centre, lower, upper, {**evidence, "shape": "box", "reason": "unseen_box_thickness"}
        centre[:2] += ((lo + hi) / 2) @ axes.T
        centre[2] = (lower[2] + upper[2]) / 2
        return centre, lower, upper, {**evidence, "shape": "box", "accepted": True,
                                    "observed_planar_extent_m": (hi - lo).tolist()}
    return centre, lower, upper, {**evidence, "reason": "no_supported_shape_prior"}


def complete_shape_height(points, name, centre, lower, upper):
    """Complete a nearly planar top using a declared generic shape prior.

    The unobserved extent is an estimate, not a depth measurement. No object
    dimensions or simulator coordinates are queried.
    """
    cylindrical = any(word in name for word in ("bowl", "mug", "bottle", "ramekin", "soup", "tomato sauce"))
    box = any(word in name for word in ("box", "cheese", "butter", "pudding", "book", "milk"))
    observed_lower, observed_upper = np.quantile(points, (.02, .98), axis=0)
    spans = observed_upper - observed_lower
    evidence = {"source": "perception_shape_prior", "observed_size_m": spans.tolist(),
                "accepted": False}
    if not (cylindrical or box) or min(spans[:2]) < .015:
        return centre, lower, upper, {**evidence, "reason": "not_a_supported_nearly_planar_top"}
    ratio = .5 if cylindrical else .4
    height = float(np.clip(ratio * min(spans[:2]), .01, .06))
    # Wrist depth on a visible top can span several millimetres. A fixed
    # 5 mm cutoff rejected the real 7-9 mm pudding measurements, despite
    # their observed height being less than half the generic box estimate.
    # Only complete a shallow surface; retain observed side/body extents.
    if spans[2] >= min(.5 * height, .01):
        return centre, lower, upper, {**evidence, "reason": "observed_vertical_extent_not_shallow",
                                     "height_prior_m": height}
    centre, lower, upper = np.array(centre, copy=True), np.array(lower, copy=True), np.array(upper, copy=True)
    lower[2] = upper[2] - height
    centre[2] = (lower[2] + upper[2]) / 2
    return centre, lower, upper, {**evidence, "accepted": True,
                                 "shape": "cylinder" if cylindrical else "box",
                                 "height_prior_m": height, "height_to_minor_width_ratio": ratio,
                                 "vertical_anchor": "observed_top", "inferred_axes": ["z"]}
