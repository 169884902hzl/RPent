# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public pan geometry diagnostics, without a placement or contact verdict.

An observed inner floor, rim, or low silhouette does not identify the hidden
underside that contacts a support. These helpers keep that distinction explicit.
They are not imported by the runtime verifier.
"""

import math

import numpy as np


def disk_rectangle_fraction(centre_xy, radius_m, lower_xy, upper_xy):
    """Area fraction of an explicit horizontal disk inside a measured XY box.

    This is geometry of the supplied disk hypothesis, not evidence that a pan's
    rim or its unobserved bottom has that support footprint.
    """
    centre = np.asarray(centre_xy, dtype=float)
    lower = np.asarray(lower_xy, dtype=float) - centre
    upper = np.asarray(upper_xy, dtype=float) - centre
    radius = float(radius_m)
    if (centre.shape != (2,) or lower.shape != (2,) or upper.shape != (2,)
            or not np.isfinite(np.r_[centre, lower, upper, radius]).all()
            or radius <= 0 or np.any(upper <= lower)):
        raise ValueError("finite positive disk and measured rectangle required")
    start, end = max(-radius, lower[0]), min(radius, upper[0])
    if start >= end or lower[1] >= radius or upper[1] <= -radius:
        return 0.0
    # Split at each circle/rectangle intersection before smooth quadrature.
    cuts = [start, end]
    for height in lower[1], upper[1]:
        if abs(height) < radius:
            crossing = math.sqrt(radius * radius - height * height)
            cuts.extend(x for x in (-crossing, crossing) if start < x < end)
    cuts = sorted(set(cuts))
    nodes, weights = np.polynomial.legendre.leggauss(96)
    area = 0.0
    for left, right in zip(cuts[:-1], cuts[1:]):
        x = (nodes + 1) * (right - left) / 2 + left
        half_height = np.sqrt(np.maximum(radius * radius - x * x, 0))
        visible = np.maximum(0, np.minimum(upper[1], half_height)
                             - np.maximum(lower[1], -half_height))
        area += float(weights @ visible) * (right - left) / 2
    return min(1.0, max(0.0, area / (math.pi * radius * radius)))


def maximum_disk_rectangle_fraction(radius_m, lower_xy, upper_xy):
    """Best centred horizontal-disk coverage for the explicit rectangle."""
    return disk_rectangle_fraction((np.asarray(lower_xy) + upper_xy) / 2,
                                   radius_m, lower_xy, upper_xy)


def observed_radial_layers(points, *, plane_origin, plane_normal, body_centre,
                           radius_m, camera_origin):
    """Describe observed layers relative to an independently fitted body plane.

    Low points are retained as observations. No hidden surface is completed,
    and no inner-floor point is promoted to a bottom-contact observation.
    """
    cloud = np.asarray(points, dtype=float)
    origin = np.asarray(plane_origin, dtype=float)
    normal = np.asarray(plane_normal, dtype=float)
    centre = np.asarray(body_centre, dtype=float)
    camera = np.asarray(camera_origin, dtype=float)
    radius = float(radius_m)
    if (cloud.ndim != 2 or cloud.shape[1] != 3
            or any(x.shape != (3,) for x in (origin, normal, centre, camera))
            or not np.isfinite(np.r_[origin, normal, centre, camera, radius]).all()
            or np.linalg.norm(normal) <= 0 or radius <= 0):
        raise ValueError("measured cloud, plane, body circle and camera required")
    cloud = cloud[np.isfinite(cloud).all(axis=1)]
    if not len(cloud):
        return {"finite_points": 0, "support_footprint": None,
                "reason": "no_finite_public_points"}
    normal = normal / np.linalg.norm(normal)
    delta = cloud - centre
    radial = np.linalg.norm(delta - np.outer(delta @ normal, normal), axis=1)
    height = (cloud - origin) @ normal
    bins = (0., .25, .5, .75, 1., 1.25, 2.)
    layers = []
    for left, right in zip(bins[:-1], bins[1:]):
        selected = (radial >= left * radius) & (radial < right * radius)
        layers.append({"radius_fraction": [left, right],
                       "observed_points": int(selected.sum()),
                       "height_quantiles_m": (np.quantile(height[selected],
                           (0., .05, .5, .95, 1.)).tolist() if selected.any() else None)})
    low = height <= np.quantile(height, .01) + .002
    return {"finite_points": len(cloud), "radial_layers": layers,
            "plane_height_quantiles_m": np.quantile(height,
                (0., .01, .05, .25, .5, .75, .95, 1.)).tolist(),
            "camera_signed_plane_distance_m": float((camera - origin) @ normal),
            "observed_low_band": {"definition": "lowest observed 1% height plus2mm",
                "points": int(low.sum()),
                "radial_quantiles_m": np.quantile(radial[low], (0., .05, .5, .95, 1.)).tolist(),
                "world_bounds": [cloud[low].min(axis=0).tolist(),
                                 cloud[low].max(axis=0).tolist()]},
            "support_footprint": None,
            "reason": "visible_surface_does_not_identify_hidden_bottom_contact"}
