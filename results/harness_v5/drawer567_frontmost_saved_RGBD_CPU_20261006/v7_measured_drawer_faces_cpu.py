"""Exact live function snapshot for public RGB-D CPU comparison only."""

import numpy as np
from robots.libero.v5_state import Entity

def measured_drawer_faces(world, parent: Entity, part: Entity, front_axis, *, moving_part=None,
                          measured_bounds_depth=False, frontmost_panel=False):
    """Fit current depth planes in measured frame borders and a drawer band.

    Bounds are an episode-local measured anchor, not simulator geometry. The
    caller must still check that the frame remains stable between captures.
    ``moving_part`` binds the moving plane to the current measured drawer,
    while ``parent`` and ``part`` retain the initial fixed-frame reference.
    Handles alone lack the height support required for a drawer face.
    """
    from robots.libero.v5_verification import vertical_face

    empty = np.empty((0, 3))
    if front_axis is None or part.part_of != parent.id:
        return {"reason": "measured_part_or_front_axis_missing"}, {"frame": empty, "moving": empty}
    front = np.asarray(front_axis, dtype=float)[:2]
    tangent = np.array((-front[1], front[0]))
    lower, upper = np.asarray(parent.lower), np.asarray(parent.upper)
    corners = np.array([(x, y) for x in (lower[0], upper[0]) for y in (lower[1], upper[1])])
    side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
    edge = np.max(corners @ front)
    # A cabinet's measured AABB can include an already extended drawer.
    # Its frontmost extent is then the drawer, not the stationary frame.
    # Search the measured cabinet depth while retaining all plane-fit gates
    # and the current selected-part binding for the moving face.
    depth_start = np.min(corners @ front) if measured_bounds_depth and moving_part is not None else edge
    if side_hi - side_lo < .08 or upper[2] - lower[2] < .09:
        return {"reason": "measured_cabinet_too_small"}, {"frame": empty, "moving": empty}
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    depth, side = points[:, :2] @ front, points[:, :2] @ tangent
    border_width = min(.025, (side_hi - side_lo) * .12)
    frame = points[(side >= side_lo) & (side <= side_hi)
                   & ((side <= side_lo + border_width) | (side >= side_hi - border_width))
                   & (points[:, 2] >= lower[2] + .015) & (points[:, 2] <= upper[2] - .015)
                   & (depth >= depth_start - .025) & (depth <= edge + .02)]
    moving = points[(side >= side_lo + border_width) & (side <= side_hi - border_width)
                    & (points[:, 2] >= part.lower[2] + .005) & (points[:, 2] <= part.upper[2] - .005)
                    & (depth >= depth_start - .03) & (depth <= edge + .35)]
    if moving_part is not None:
        if (moving_part.id != part.id or moving_part.part_of != parent.id
                or not moving_part.visible):
            return {"reason": "current_selected_drawer_identity_missing"}, {"frame": empty, "moving": empty}
        # An open drawer exposes a larger static cabinet plane in the same
        # ordinal band. Point count alone does not identify the moving part.
        # Bind its fit to the current publicly measured part before ranking
        # plane support; the fixed reference keeps its original bounds.
        moving = moving[((moving >= np.asarray(moving_part.lower) - .005)
                         & (moving <= np.asarray(moving_part.upper) + .005)).all(axis=1)]
    clouds, fits = {}, {}
    for key, cloud in (("frame", frame), ("moving", moving)):
        best, best_cloud = None, empty
        if len(cloud) >= 30:
            projection = cloud[:, :2] @ front
            # Quantized depth has repeated pixels. Fit the best supported
            # actual plane, rather than averaging drawer face and handle.
            bins = np.arange(depth_start - .031, edge + .356, .004)
            histogram, edges = np.histogram(projection, bins=bins)
            for index in np.argsort(histogram)[-5:]:
                if histogram[index] < 30:
                    continue
                centre = (edges[index] + edges[index + 1]) / 2
                selected = cloud[np.abs(projection - centre) <= .004]
                fit = vertical_face(selected)
                if fit is None or abs(np.asarray(fit["normal_xy"]) @ front) < .95:
                    continue
                if key == "frame" and (
                        np.ptp(selected[:, :2] @ tangent) < .65 * (side_hi - side_lo)
                        or np.ptp(selected[:, 2]) < .6 * (upper[2] - lower[2])):
                    continue
                if key == "moving" and frontmost_panel:
                    # A wider front panel and a dense inner strip can both
                    # pass a plane fit. Point count alone selects the strip
                    # in original t8/s18 (1272 versus 1262 points). Bind the
                    # moving panel to a broad, outward-facing measured face.
                    if np.ptp(selected[:, :2] @ tangent) < .5 * (side_hi - side_lo):
                        continue
                    better = (best is None or
                              np.asarray(fit["centre"])[:2] @ front >
                              np.asarray(best["centre"])[:2] @ front)
                else:
                    better = best is None or len(selected) > len(best_cloud)
                if better:
                    best, best_cloud = fit, selected
        fits[key], clouds[key] = best, best_cloud
    return {**fits, "basis": ("current_rgbd_frontmost_broad_selected_drawer/7-dev" if frontmost_panel else
                             "current_rgbd_measured_bounds_selected_drawer/5-dev"
                             if measured_bounds_depth and moving_part is not None else
                             "current_rgbd_selected_drawer_and_fixed_border/4-dev"
                             if moving_part is not None else "current_rgbd_measured_border_and_drawer_band/3-dev"),
            **({"depth_search_m": [float(depth_start - .031), float(edge + .356)],
                "depth_search_source": "perception_parent_bounds"}
               if measured_bounds_depth and moving_part is not None else {}),
            "anchor_parent": parent.id, "anchor_part": part.id,
            "anchor_source_step": parent.source_step,
            **({"moving_panel_rank": "outward_depth_after_existing_fit_gates",
                "moving_panel_min_frame_width_fraction": .5} if frontmost_panel else {}),
            **({"current_part": moving_part.id, "current_part_source_step": moving_part.source_step,
                "current_part_bounds": {"lower": list(moving_part.lower), "upper": list(moving_part.upper)},
                "binding_margin_m": .005} if moving_part is not None else {}),
            "point_counts": {key: len(cloud) for key, cloud in clouds.items()}}, clouds
