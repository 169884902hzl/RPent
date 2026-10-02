# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Geometry estimated from calibrated, segmented RGB-D measurements only."""

from __future__ import annotations

import numpy as np


def measured_points(world, mask):
    """Drop missing depths; camera-to-world conversion belongs to capture."""
    points = np.asarray(world)[mask].astype(float)
    return points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]


def fuse_cloud(primary, secondary, *, max_gap=.08):
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
    # Equal spatial resolution keeps a dense close-up from erasing the main
    # camera's surface. Voxel centroids still contain measured points only.
    cloud = np.concatenate((primary, points))
    bins = np.floor(cloud / .002).astype(np.int64)
    _, inverse = np.unique(bins, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    cloud = np.column_stack([np.bincount(inverse, weights=cloud[:, i]) / counts for i in range(3)])
    return cloud, index, {"fused": True, "matching_views": 1,
                          "primary_points": len(primary), "secondary_points": len(points),
                          "voxel_points": len(cloud), "secondary_score": score}


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
