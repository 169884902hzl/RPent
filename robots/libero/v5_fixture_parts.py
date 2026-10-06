# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Furniture surfaces derived from the visible parent's RGB-D point cloud."""

import math

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


def measured_microwave_door(parent: Entity, points) -> tuple[dict | None, dict]:
    """Associate one measured planar door adjacent to the appliance shell."""
    from robots.libero.v5_verification import vertical_face

    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    face = vertical_face(points)
    if face is None:
        return None, {"reason": "door_plane_not_measured"}
    lower, upper = np.quantile(points, (.02, .98), axis=0)
    gap = np.maximum(0, np.maximum(np.asarray(parent.lower[:2]) - upper[:2],
                                  lower[:2] - parent.upper[:2]))
    if (np.linalg.norm(gap) > .06 or lower[2] < parent.lower[2] - .03
            or upper[2] > parent.upper[2] + .03):
        return None, {"reason": "door_not_adjacent_to_measured_shell", "plane": face}
    return {"name": "microwave door", "xyz": tuple(np.median(points, axis=0)),
            "lower": tuple(lower), "upper": tuple(upper),
            "geometry": "measured_door_surface"}, {"basis": "distinct_sam_door_rgbd/6-dev", "plane": face}


def measured_microwave_frame(world, parent: Entity, camera_xyz, moving_mask, moving_face, anchor=None):
    """Track a visible shell-front patch independently of an open door.

    Establish a reference only when a separately measured open door supplies
    a distinct plane. Later captures use that observed patch, not the newly
    visible closed door. Missing or nonplanar points leave the frame unknown.
    """
    from robots.libero.v5_verification import vertical_face

    world = np.asarray(world, dtype=float)
    points = world.reshape(-1, 3)
    valid = np.isfinite(points).all(axis=1)
    if moving_mask is not None:
        valid &= ~np.asarray(moving_mask, dtype=bool).reshape(-1)
    evidence = {"basis": "current_rgbd_at_initial_observed_shell_front_patch/8-dev"}
    if anchor is None:
        lo, hi = np.asarray(parent.lower), np.asarray(parent.upper)
        extents = hi[:2] - lo[:2]
        normal_axis = int(np.argmin(extents))
        if (camera_xyz is None or moving_face is None or min(extents) <= .02
                or max(extents) / min(extents) < 1.5):
            return None, {**evidence, "reason": "distinct_open_door_or_shell_profile_missing"}, points[:0], None
        edge = lo[normal_axis] if camera_xyz[normal_axis] < parent.xyz[normal_axis] else hi[normal_axis]
        valid &= ((points >= lo - .002) & (points <= hi + .002)).all(axis=1)
        valid &= ((abs(points[:, normal_axis] - edge) <= .008)
                  & (points[:, 2] >= lo[2] + .01) & (points[:, 2] <= hi[2] - .01))
    else:
        lo, hi = np.asarray(anchor["lower"]), np.asarray(anchor["upper"])
        valid &= ((points >= lo - .002) & (points <= hi + .002)).all(axis=1)
    cloud = points[valid]
    fit = vertical_face(cloud)
    if fit is None:
        return None, {**evidence, "reason": "fixed_front_patch_not_measured"}, cloud, anchor
    if anchor is None:
        cosine = abs(np.asarray(fit["normal_xy"]) @ np.asarray(moving_face["normal_xy"]))
        if cosine > math.cos(math.radians(30)):
            return None, {**evidence, "reason": "initial_front_not_distinct_from_moving_door"}, cloud, None
        lo, hi = np.quantile(cloud, (.02, .98), axis=0)
        anchor = {"lower": lo.tolist(), "upper": hi.tolist(),
                  "source_step": parent.source_step, "parent": parent.id}
    return fit, {**evidence, "anchor": anchor}, cloud, anchor


def adjacent_panel_prompt(world, parent: Entity) -> tuple[list[int] | None, dict]:
    """Find a unique observed panel to prompt SAM when its text query misses.

    The hint is not a door label. SAM must segment it and the existing door
    measurement must still establish a plane adjacent to the measured shell.
    """
    from scipy.ndimage import distance_transform_edt, label

    world = np.asarray(world, dtype=float)
    lo, hi = np.asarray(parent.lower), np.asarray(parent.upper)
    gap = np.maximum(0, np.maximum(lo[:2] - world[..., :2], world[..., :2] - hi[:2]))
    outside = ~np.all((world[..., :2] >= lo[:2] - .01) & (world[..., :2] <= hi[:2] + .01), axis=-1)
    available = np.isfinite(world).all(axis=-1) & (np.linalg.norm(gap, axis=-1) <= .25) & outside
    available &= (world[..., 2] >= lo[2] - .015) & (world[..., 2] <= hi[2] + .015)
    rng = np.random.default_rng(0)
    panels, diagnostics = [], []
    for _ in range(5):
        cloud = world[available]
        if len(cloud) < 60:
            break
        sample = cloud[rng.choice(len(cloud), min(len(cloud), 4000), replace=False)]
        pairs = rng.choice(len(sample), (128, 2), replace=True)
        vectors = sample[pairs[:, 1], :2] - sample[pairs[:, 0], :2]
        norms = np.linalg.norm(vectors, axis=-1)
        if not np.any(norms > .05):
            break
        normals = np.stack([-vectors[:, 1], vectors[:, 0]], axis=-1)[norms > .05] / norms[norms > .05, None]
        anchors = sample[pairs[norms > .05, 0], :2]
        distances = np.abs(np.einsum("nmi,mi->nm", sample[:, None, :2] - anchors, normals))
        best = int(np.argmax(np.sum(distances <= .004, axis=0)))
        plane = available & (np.abs((world[..., :2] - anchors[best]) @ normals[best]) <= .004)
        available &= ~plane
        components, count = label(plane)
        for component in range(1, count + 1):
            mask = components == component
            if np.count_nonzero(mask) < 60:
                continue
            measured, evidence = measured_microwave_door(parent, world[mask])
            if measured is None:
                continue
            height = measured["upper"][2] - measured["lower"][2]
            # A small mug wall next to the fixture is not its full-height door.
            if height < .65 * (hi[2] - lo[2]):
                continue
            panels.append(mask)
            diagnostics.append({"measurement": measured, "plane": evidence["plane"],
                                "pixels": int(mask.sum())})
    evidence = {"basis": "current_rgbd_unique_adjacent_panel_point/7-dev",
                "source": "perception", "panels": diagnostics}
    if len(panels) != 1:
        return None, {**evidence, "reason": "adjacent_panel_missing_or_ambiguous"}
    point = list(map(int, np.unravel_index(np.argmax(distance_transform_edt(panels[0])), panels[0].shape)))
    return point, {**evidence, "point": point}


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


def measured_handle_front(world, parent: Entity):
    """Identify a closed cabinet's front from repeated measured handle rows.

    A flat closed front has no drawer-depth change between height bands. Look
    for elongated protrusions in at least two bands of the current RGB-D
    capture. A single nearby shelf or rack is insufficient evidence.
    """
    cloud = np.asarray(world).reshape(-1, 3)
    cloud = cloud[np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)]
    lower, upper = np.asarray(parent.lower), np.asarray(parent.upper)
    edges = np.linspace(lower[2], upper[2] - .025, 4)
    candidates, profiles = [], []
    for axis in (0, 1):
        other = 1 - axis
        for sign in (-1, 1):
            edge = sign * (upper[axis] if sign == 1 else lower[axis])
            distance = sign * cloud[:, axis] - edge
            keep = ((distance >= .015) & (distance <= .075)
                    & (cloud[:, other] >= lower[other] - .003)
                    & (cloud[:, other] <= upper[other] + .003)
                    & (cloud[:, 2] >= lower[2] + .01)
                    & (cloud[:, 2] <= upper[2] - .025))
            points = cloud[keep]
            rows = []
            for k in range(3):
                band = points[(points[:, 2] >= edges[k]) & (points[:, 2] < edges[k + 1])]
                if len(band) < 30:
                    continue
                lo, hi = np.quantile(band, (.05, .95), axis=0)
                if hi[other] - lo[other] < .04 or hi[2] - lo[2] > .025:
                    continue
                rows.append({"band": k, "points": len(band),
                             "centre": np.median(band, axis=0).tolist(),
                             "width_m": float(hi[other] - lo[other]),
                             "height_m": float(hi[2] - lo[2])})
            # One handle crossing a height-band boundary is still one row.
            distinct = []
            for row in rows:
                if distinct and row["centre"][2] - distinct[-1]["centre"][2] < .035:
                    if row["points"] > distinct[-1]["points"]:
                        distinct[-1] = row
                else:
                    distinct.append(row)
            normal = [0., 0., 0.]
            normal[axis] = float(sign)
            profiles.append({"axis": normal, "handle_rows": distinct})
            if len(distinct) >= 2:
                candidates.append((tuple(normal), points))
    evidence = {"basis": "current_rgbd_repeated_handle_rows/3-dev", "profiles": profiles}
    if len(candidates) != 1:
        return None, {**evidence, "reason": "handles_not_unique_or_not_measured"}, cloud[:0]
    normal, handles = candidates[0]
    return normal, evidence, handles


def measured_drawer_faces(world, parent: Entity, part: Entity, front_axis):
    """Fit current depth planes in measured frame borders and a drawer band.

    Bounds are an episode-local measured anchor, not simulator geometry. The
    caller must still check that the frame remains stable between captures.
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
    if side_hi - side_lo < .08 or upper[2] - lower[2] < .09:
        return {"reason": "measured_cabinet_too_small"}, {"frame": empty, "moving": empty}
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    depth, side = points[:, :2] @ front, points[:, :2] @ tangent
    border_width = min(.025, (side_hi - side_lo) * .12)
    frame = points[(side >= side_lo) & (side <= side_hi)
                   & ((side <= side_lo + border_width) | (side >= side_hi - border_width))
                   & (points[:, 2] >= lower[2] + .015) & (points[:, 2] <= upper[2] - .015)
                   & (depth >= edge - .025) & (depth <= edge + .02)]
    moving = points[(side >= side_lo + border_width) & (side <= side_hi - border_width)
                    & (points[:, 2] >= part.lower[2] + .005) & (points[:, 2] <= part.upper[2] - .005)
                    & (depth >= edge - .03) & (depth <= edge + .35)]
    clouds, fits = {}, {}
    for key, cloud in (("frame", frame), ("moving", moving)):
        best, best_cloud = None, empty
        if len(cloud) >= 30:
            projection = cloud[:, :2] @ front
            # Quantized depth has repeated pixels. Fit the best supported
            # actual plane, rather than averaging drawer face and handle.
            bins = np.arange(edge - .031, edge + .356, .004)
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
                if best is None or len(selected) > len(best_cloud):
                    best, best_cloud = fit, selected
        fits[key], clouds[key] = best, best_cloud
    return {**fits, "basis": "current_rgbd_measured_border_and_drawer_band/3-dev",
            "anchor_parent": parent.id, "anchor_part": part.id,
            "anchor_source_step": parent.source_step,
            "point_counts": {key: len(cloud) for key, cloud in clouds.items()}}, clouds


def measured_drawer_handle(world, parent: Entity, part: Entity, front_axis):
    """Measure the selected handle protrusion relative to its current face."""
    empty = np.empty((0, 3))
    faces, _ = measured_drawer_faces(world, parent, part, front_axis)
    evidence = {"basis": "current_rgbd_selected_drawer_handle/1-dev",
                "moving_face": faces.get("moving"), "anchor_part": part.id}
    if front_axis is None or not faces.get("moving"):
        return None, {**evidence, "reason": "selected_drawer_face_not_measured"}, empty
    front = np.asarray(front_axis, dtype=float)[:2]
    front /= np.linalg.norm(front)
    tangent = np.array((-front[1], front[0]))
    points = np.asarray(world, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    corners = np.array([(x, y) for x in (parent.lower[0], parent.upper[0])
                        for y in (parent.lower[1], parent.upper[1])])
    side_lo, side_hi = np.min(corners @ tangent), np.max(corners @ tangent)
    protrusion = (points[:, :2] - np.asarray(faces["moving"]["centre"])[:2]) @ front
    band = points[(protrusion >= .012) & (protrusion <= .09)
                  & (points[:, :2] @ tangent >= side_lo + .015)
                  & (points[:, :2] @ tangent <= side_hi - .015)
                  & (points[:, 2] >= part.lower[2] + .005)
                  & (points[:, 2] <= part.upper[2] - .005)]
    if len(band) < 10:
        return None, {**evidence, "reason": "selected_handle_depth_missing",
                      "points": len(band)}, band
    lo, hi = np.quantile(band, (.05, .95), axis=0)
    width = float(np.ptp(band[:, :2] @ tangent))
    if width < .025 or hi[2] - lo[2] > .035:
        return None, {**evidence, "reason": "handle_protrusion_not_one_thin_row",
                      "points": len(band), "width_m": width,
                      "height_m": float(hi[2] - lo[2])}, band
    pose = {"xyz": np.median(band, axis=0).tolist(),
            "approach_normal_xy": front.tolist(), "handle_tangent_xy": tangent.tolist()}
    return pose, {**evidence, "points": len(band), "width_m": width,
                  "height_m": float(hi[2] - lo[2])}, band


def fuse_drawer_handle_clouds(primary, secondary, front_axis):
    """Associate overlapping views of the same measured thin handle row.

    A wrist close-up may only see one end of a handle. Its pixel-weighted
    median then differs from the full view although the measured surfaces
    overlap. Compare that overlap and the normal/height coordinates before
    equalizing spatial density; a different drawer or depth plane stays out.
    """
    from robots.libero.v5_perception_geometry import fuse_cloud

    front = np.asarray(front_axis, dtype=float)[:2]
    front /= np.linalg.norm(front)
    basis = np.array([[-front[1], front[0], 0.], [*front, 0.], [0., 0., 1.]])
    bounds = [np.quantile(np.asarray(cloud) @ basis.T, (.05, .95), axis=0)
              for cloud in (primary, secondary)]
    overlap = float(min(bounds[0][1, 0], bounds[1][1, 0])
                    - max(bounds[0][0, 0], bounds[1][0, 0]))
    centres = [(lo + hi) / 2 for lo, hi in bounds]
    depth_gap, height_gap = np.abs(centres[0] - centres[1])[1:]
    evidence = {"basis": "current_rgbd_overlapping_handle_row/2-dev",
                "tangent_overlap_m": overlap, "normal_distance_m": float(depth_gap),
                "height_distance_m": float(height_gap)}
    if overlap < .01 or depth_gap > .01 or height_gap > .01:
        return None, {**evidence, "reason": "handle_surfaces_do_not_overlap"}
    points, index, fusion = fuse_cloud(primary, [(secondary, 1.)], trim_depth_tails=True)
    if index is None:
        return None, {**evidence, "fusion": fusion, "reason": "handle_depth_fusion_failed"}
    return points, {**evidence, "fusion": fusion}


def measured_stove_control_pose(points, parent: Entity, camera_xyz):
    """Fit the visible control surface, never infer a knob from burner bounds.

    A small SAM control mask still needs current depth, attachment to the
    measured stove and a supported surface normal. The normal is three
    dimensional: a horizontal stove control must not become a fictitious
    vertical drawer handle merely because the approach API used xy normals.
    """
    cloud = np.asarray(points, dtype=float).reshape(-1, 3)
    cloud = cloud[np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)]
    evidence = {"basis": "current_rgbd_stove_control_surface/1-dev", "points": len(cloud),
                "source": "perception", "endpoint_state": "unmeasured"}
    if parent.name != "stove" or len(cloud) < 20:
        return None, {**evidence, "reason": "current_stove_control_depth_missing"}
    lower, upper = np.quantile(cloud, (.02, .98), axis=0)
    extents = upper - lower
    gap = np.maximum(0, np.maximum(np.asarray(parent.lower) - upper,
                                  lower - np.asarray(parent.upper)))
    evidence.update(lower=lower.tolist(), upper=upper.tolist(),
                    measured_shell_gap_m=float(np.linalg.norm(gap)))
    if np.linalg.norm(gap) > .07:
        return None, {**evidence, "reason": "control_not_adjacent_to_measured_stove"}
    if max(extents) > .13:
        return None, {**evidence, "reason": "control_mask_includes_large_fixture_surface"}
    centre = np.median(cloud, axis=0)
    _, singular, axes = np.linalg.svd(cloud - centre, full_matrices=False)
    normal, tangent = axes[-1].copy(), axes[0].copy()
    residual = float(np.quantile(np.abs((cloud - centre) @ normal), .9))
    plane_support = float(singular[1] / np.sqrt(len(cloud)))
    evidence.update(surface_residual_p90_m=residual, transverse_support_m=plane_support,
                    singular_values=singular.tolist())
    if residual > .004 or plane_support < .002:
        return None, {**evidence, "reason": "control_surface_orientation_not_measured"}
    camera_xyz = np.asarray(camera_xyz, dtype=float)
    if normal @ (camera_xyz - centre) < 0:
        normal = -normal
    pose = {"xyz": centre.tolist(), "approach_normal_xyz": normal.tolist(),
            "approach_normal_xy": normal[:2].tolist(),
            "handle_tangent_xyz": tangent.tolist(), "handle_tangent_xy": tangent[:2].tolist()}
    return pose, evidence


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
        # Use the measured cabinet extent as the ordinal reference. Re-binning
        # an occluded fragment can turn its bottom drawer into a top drawer or
        # advertise a side patch as the cabinet's top surface.
        cabinet_lo, cabinet_hi = parent.lower[2], parent.upper[2]
        edges = np.linspace(cabinet_lo, cabinet_hi, 4)
        drawer_points = points[points[:, 2] < cabinet_hi - .01]
        drawer_face = face[face[:, 2] < cabinet_hi - .01]
        for index, label in enumerate(("bottom", "middle", "top")):
            pool = drawer_points if calibrated_front else drawer_face
            band = pool[(pool[:, 2] >= edges[index]) & (pool[:, 2] <= edges[index + 1])]
            if calibrated_front:
                band = band[band @ front >= np.quantile(band @ front, .65)] if front is not None and len(band) else points[:0]
            # A horizontal shelf or a handle alone does not measure a drawer
            # face, even when it happens to fall in the right height band.
            if len(band) and np.ptp(band[:, 2]) < .015:
                band = points[:0]
            groups.append((f"cabinet {label} drawer", band, "measured_front_band"))
        groups.append(("cabinet top surface", points[points[:, 2] >= cabinet_hi - .01], "measured_top_surface"))
    elif parent.name == "microwave":
        # A shell segmentation includes side walls, its cavity and often the
        # open door. Cabinet-front calibration does not identify a microwave
        # moving panel. Its door must come from the independent door mask and
        # measured_microwave_door path, not this generic shell decomposition.
        return []
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
