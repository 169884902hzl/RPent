# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public RGB-D component and handle measurements for grasp development."""
from __future__ import annotations

import numpy as np

VERSION = 'public-grasp-geometry/1-dev'


def complete_planar_boundary(world, mask, *, max_step_m=.003, max_residual_m=.001):
    """Recover one omitted edge pixel on a measured local two-axis surface."""
    from scipy.ndimage import binary_dilation

    world, mask = np.asarray(world), np.asarray(mask, bool)
    valid = np.isfinite(world).all(axis=2) & (np.linalg.norm(world, axis=2) > 1e-6)
    ring = binary_dilation(mask) & ~mask & valid
    result, added = mask.copy(), 0
    for y, x in zip(*np.nonzero(ring)):
        ys, xs = slice(max(0, y-3), y+4), slice(max(0, x-3), x+4)
        local = world[ys, xs][(mask & valid)[ys, xs]]
        if len(local) < 6 or np.linalg.norm(local-world[y, x], axis=1).min() > max_step_m:
            continue
        centre = local.mean(axis=0)
        _, spread, axes = np.linalg.svd(local-centre, full_matrices=False)
        # Two measured tangent directions are required; a line of rim pixels
        # alone cannot establish a plane on the far side of a depth edge.
        if (spread[1]/np.sqrt(len(local)) <= max_step_m/10
                or spread[2]/np.sqrt(len(local)) > max_residual_m
                or abs((world[y, x]-centre) @ axes[-1]) > max_residual_m):
            continue
        result[y, x] = True
        added += 1
    return result, {'version': 'public-local-plane-instance-boundary/1-dev',
        'candidate_pixels': int(ring.sum()), 'added_pixels': added,
        'max_step_m': max_step_m, 'max_residual_m': max_residual_m,
        'source': 'current_instance_mask_and_same_view_local_rgbd_plane',
        'private_target_pose_used': False}


def complete_crossview_boundary(world, mask, other_world, other_mask, other_metadata,
                                *, max_step_m=.003, max_depth_residual_m=.001):
    """Associate omitted surface pixels using another current target view.

    Candidates must match an opposite-view surface connected to pixels
    already shared by both instance masks, within the existing 3 mm limit.
    Their projection must lie in the other target
    mask (or its silhouette against deeper background), with a target depth
    sample within one pixel and 1 mm in depth.
    A nearby obstacle is never removed solely by nearest-target distance.
    """
    world, other_world = np.asarray(world), np.asarray(other_world)
    mask, other_mask = np.asarray(mask, bool), np.asarray(other_mask, bool)
    valid = np.isfinite(world).all(axis=2) & (np.linalg.norm(world, axis=2) > 1e-6)
    # A surface can be separated by a self-occlusion depth edge in this view
    # and continuous in the other view. Require its other-view component to
    # overlap the existing instance; a disconnected adjacent object cannot
    # acquire ownership merely from a broad semantic mask.
    from scipy.spatial import cKDTree
    labels, _ = depth_components(other_world, other_mask, max_gap_m=max_step_m)
    other_pixels = np.flatnonzero(labels >= 0)
    shared_labels = []
    if len(other_pixels) and (mask & valid).any():
        distances, indices = cKDTree(other_world.reshape(-1, 3)[other_pixels]).query(world[mask & valid])
        shared_labels = np.unique(labels.flat[other_pixels[indices[distances <= max_step_m]]])
    other_mask = np.isin(labels, shared_labels) & (labels >= 0)
    other_points = other_world[other_mask]
    other_points = other_points[np.isfinite(other_points).all(axis=1)]
    eligible = np.zeros(mask.shape, bool)
    if len(other_points):
        eligible = (valid & ~mask & (world >= other_points.min(0)-max_step_m).all(axis=2)
                    & (world <= other_points.max(0)+max_step_m).all(axis=2))
    pixels = np.flatnonzero(eligible)
    intrinsic = np.array(other_metadata['intrinsic_K'], dtype=float)
    intrinsic[0] *= other_world.shape[1] / other_metadata['width']
    intrinsic[1] *= other_world.shape[0] / other_metadata['height']
    inverse = np.linalg.inv(np.asarray(other_metadata['extrinsic_cam2world']))
    points = world.reshape(-1, 3)[pixels]
    camera = (np.c_[points, np.ones(len(points))] @ inverse.T)[:, :3]
    projected = camera @ intrinsic.T
    positive = camera[:, 2] > 1e-5
    uv = np.zeros((len(points), 2))
    uv[positive] = projected[positive, :2] / projected[positive, 2:3]
    xy = np.rint(uv).astype(int)
    height, width = other_mask.shape
    inside = positive & (xy[:, 0] >= 0) & (xy[:, 0] < width) & (xy[:, 1] >= 0) & (xy[:, 1] < height)
    ids = np.flatnonzero(inside)
    nearest = other_world[xy[ids, 1], xy[ids, 0]]
    nearest_depth = (np.c_[nearest, np.ones(len(ids))] @ inverse.T)[:, 2]
    # Rounding at a silhouette can land on distant background while the
    # adjacent pixel measures this target surface. Permit that case only;
    # an unlabelled surface at the projected depth is not target evidence.
    central_identity = (other_mask[xy[ids, 1], xy[ids, 0]]
                        | (nearest_depth > camera[ids, 2]+max_step_m))
    inside[ids] &= (np.isfinite(nearest).all(axis=1)
                    & central_identity
                    & (nearest_depth >= camera[ids, 2]-max_step_m))
    accepted = np.zeros(len(points), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            x, y = xy[:, 0]+dx, xy[:, 1]+dy
            ids = np.flatnonzero(inside & (x >= 0) & (x < width) & (y >= 0) & (y < height))
            if not len(ids):
                continue
            observed = other_world[y[ids], x[ids]]
            depth = (np.c_[observed, np.ones(len(ids))] @ inverse.T)[:, 2]
            supported = (other_mask[y[ids], x[ids]] & np.isfinite(observed).all(axis=1)
                & (np.abs(depth-camera[ids, 2]) <= max_depth_residual_m)
                & (np.linalg.norm(observed-points[ids], axis=1) <= max_step_m))
            accepted[ids] |= supported
    result = mask.copy()
    result.flat[pixels[accepted]] = True
    return result, {'version': 'public-crossview-instance-boundary/3-dev',
        'candidate_pixels': len(pixels), 'added_pixels': int((result & ~mask).sum()),
        'shared_opposite_view_components': [int(label) for label in shared_labels],
        'max_step_m': max_step_m, 'max_depth_residual_m': max_depth_residual_m,
        'source': 'paired_current_target_masks_rgbd_and_public_camera_calibration',
        'private_target_pose_used': False}


def complete_instance_boundary(world, mask, *, rounds=3, max_step_m=.003,
                               max_extrapolation_error_m=.001, measured_tangent_spacing=False):
    """Recover a narrow omitted rim only along a measured continuous surface.

    Each added pixel needs two consecutive interior pixels and must agree
    with their 3-D linear extrapolation. A depth jump to a table or neighbour
    is retained as scene geometry. This is image-space instance refinement,
    not a nearest-neighbour carve of the collision cloud. With measured
    tangent spacing, a grazing surface may have larger per-pixel spacing;
    its next step must agree with the two measured interior samples within
    the same extrapolation error. Callers must independently retain static
    scene membership when using this option for moving payloads.
    """
    world, mask = np.asarray(world), np.asarray(mask, dtype=bool)
    valid = np.isfinite(world).all(axis=2) & (np.linalg.norm(world, axis=2) > 1e-6)
    current = mask & valid
    added = []
    for _ in range(rounds):
        extended = np.zeros(mask.shape, dtype=bool)
        for dy, dx in ((0,1), (0,-1), (1,0), (-1,0)):
            # Slice a candidate and the two pixels directed into the instance.
            y0, y1 = max(0,2*dy), mask.shape[0] + min(0,2*dy)
            x0, x1 = max(0,2*dx), mask.shape[1] + min(0,2*dx)
            a = (slice(y0,y1), slice(x0,x1))
            b = (slice(y0-dy,y1-dy), slice(x0-dx,x1-dx))
            c = (slice(y0-2*dy,y1-2*dy), slice(x0-2*dx,x1-2*dx))
            eligible = valid[a] & ~current[a] & current[b] & current[c]
            ids = np.nonzero(eligible)
            if not len(ids[0]):
                continue
            candidate, near, inner = world[a][ids], world[b][ids], world[c][ids]
            step = near-inner
            continuous = np.linalg.norm(candidate-(near+step),axis=1) <= max_extrapolation_error_m
            if not measured_tangent_spacing:
                continuous &= ((np.linalg.norm(step,axis=1) <= max_step_m)
                               & (np.linalg.norm(candidate-near,axis=1) <= max_step_m))
            extended[a][ids] |= continuous
        added.append(int(extended.sum()))
        current |= extended
    return current, {'version':'public-depth-continuous-instance-boundary/1-dev',
        'source':'current_instance_mask_and_same_view_rgbd',
        'input_pixels':int(np.count_nonzero(mask)), 'added_pixels_per_round':added,
        'rounds':rounds, 'max_step_m':None if measured_tangent_spacing else max_step_m,
        'spacing_source': 'measured_two_pixel_tangent' if measured_tangent_spacing else 'fixed_metric_limit',
        'max_extrapolation_error_m':max_extrapolation_error_m,
        'private_target_pose_used':False}


def measured_grasp_regions(points, name):
    """Perception-only category exception: identify a pan's narrow handle.

    Other objects share surface samples and PCA; no category selects an
    executor, grasp method, route, force or budget here.
    """
    cloud = np.asarray(points, dtype=float)
    cloud = cloud[np.isfinite(cloud).all(axis=1)]
    evidence = {'version': VERSION, 'source': 'public_rgbd', 'category_exception': None}
    if any(word in name.lower() for word in ('frypan', 'frying pan', 'skillet')):
        measured, handle = measure_pan_handle(cloud)
        evidence.update(category_exception='pan_handle_surface_segmentation', handle=handle)
        if measured is None:
            return None, {**evidence, 'reason': 'pan_handle_not_measured'}
        cloud = measured['points']
    if len(cloud) < 40:
        return None, {**evidence, 'reason': 'insufficient_measured_surface'}
    lower, upper = np.quantile(cloud, [.02, .98], axis=0)
    _, axes = np.linalg.eigh(np.cov(cloud[:, :2].T))
    centre = np.median(cloud, axis=0)
    seeds = [np.array([*centre[:2], np.quantile(cloud[:, 2], q)]) for q in (.35, .60, .80)]
    top = cloud[cloud[:, 2] >= np.quantile(cloud[:, 2], .8)]
    for angle in np.linspace(0., 2*np.pi, 8, endpoint=False):
        direction = np.array([np.cos(angle), np.sin(angle)])
        point = top[np.argmax((top[:, :2]-centre[:2])@direction)]
        seeds.append(point)
    evidence.update(lower=lower.tolist(), upper=upper.tolist(), measured_points=len(cloud))
    return {'points': cloud, 'seeds': seeds, 'closing_axis_xy': axes[:, 0],
            'top_z': float(upper[2])}, evidence


def oblique_target_view(before, narrow_axis, eef_xyz, body_quat_xyzw, camera_meta, sign):
    """Aim the calibrated wrist camera at a stationary measured target flank."""
    from scipy.spatial.transform import Rotation

    axis = np.asarray(narrow_axis, dtype=float)
    axis /= np.linalg.norm(axis)
    extrinsic = np.asarray(camera_meta['extrinsic_cam2world'], dtype=float)
    body = Rotation.from_quat(body_quat_xyzw).as_matrix()
    camera_in_body = body.T @ extrinsic[:3, :3]
    camera_offset = body.T @ (extrinsic[:3, 3] - np.asarray(eef_xyz))
    target = (np.asarray(before.lower) + before.upper) / 2
    camera_position = np.array([*target[:2], before.upper[2] + .17])
    camera_position[:2] += sign * .12 * axis
    forward = target - camera_position
    forward /= np.linalg.norm(forward)
    right = extrinsic[:3, 0] - forward * np.dot(extrinsic[:3, 0], forward)
    right /= np.linalg.norm(right)
    camera_rotation = np.c_[right, np.cross(forward, right), forward]
    desired_body = camera_rotation @ camera_in_body.T
    return {'xyz': (camera_position - desired_body @ camera_offset).tolist(),
            'body_quat_xyzw': Rotation.from_matrix(desired_body).as_quat().tolist(),
            'camera_xyz': camera_position.tolist(), 'look_at_xyz': target.tolist(),
            'source': 'measured_box_bounds_and_public_wrist_calibration', 'sign': sign,
            'private_pose_used': False}


oblique_box_view = oblique_target_view


def depth_components(world, mask, *, max_gap_m=.012):
    """Split a pixel mask at measured 3-D discontinuities, including diagonal gaps."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    world, mask = np.asarray(world), np.asarray(mask, dtype=bool)
    valid = mask & np.isfinite(world).all(axis=2) & (np.linalg.norm(world, axis=2) > 1e-6)
    labels = np.full(mask.shape, -1, dtype=int)
    pixels = np.flatnonzero(valid)
    if not len(pixels):
        return labels, []
    labels.flat[pixels] = np.arange(len(pixels))
    first, second = [], []
    for dy, dx in ((0, 1), (1, 0)):
        a, b = (slice(0, -dy or None), slice(0, -dx or None)), (slice(dy, None), slice(dx, None))
        linked = valid[a] & valid[b] & (np.linalg.norm(world[a] - world[b], axis=2) <= max_gap_m)
        first.append(labels[a][linked]); second.append(labels[b][linked])
    i, j = np.concatenate(first), np.concatenate(second)
    graph = coo_matrix((np.ones(len(i)), (i, j)), shape=(len(pixels), len(pixels)))
    count, components = connected_components(graph, directed=False)
    labels.flat[pixels] = components
    sizes = np.bincount(components, minlength=count)
    return labels, sizes.tolist()


def clean_object_mask(world, mask, *, prior_lower=None, prior_upper=None, max_gap_m=.012):
    """Keep one depth-connected instance; a stationary prior forbids distant rebinding."""
    world = np.asarray(world)
    labels, sizes = depth_components(world, mask, max_gap_m=max_gap_m)
    evidence = {'version': VERSION, 'source': 'perception', 'max_gap_m': max_gap_m, 'components': []}
    choices = []
    for label, count in enumerate(sizes):
        if count < 30:
            evidence['components'].append({'label': label, 'points': count, 'rejected': 'too_few_depth_points'})
            continue
        points = world[labels == label]
        lower, upper = np.quantile(points, (.02, .98), axis=0)
        detail = {'label': label, 'points': count, 'lower': lower.tolist(), 'upper': upper.tolist()}
        overlap = None
        if prior_lower is not None and prior_upper is not None:
            overlap = float(np.mean(((points >= np.asarray(prior_lower) - .015)
                                     & (points <= np.asarray(prior_upper) + .015)).all(axis=1)))
            detail['stationary_prior_fraction'] = overlap
            if overlap < .5:
                detail['rejected'] = 'outside_stationary_measured_identity'
        evidence['components'].append(detail)
        if 'rejected' not in detail:
            choices.append((count if overlap is None else count * overlap, label))
    if not choices:
        return np.zeros(labels.shape, dtype=bool), {**evidence, 'selected': None, 'reason': 'no_supported_component'}
    label = max(choices)[1]
    result = labels == label
    evidence.update(selected=label, retained_pixels=int(result.sum()), input_pixels=int(np.count_nonzero(mask)))
    return result, evidence


def measure_pan_handle(points):
    """Find a connected, narrow extension beyond the measured round pan body."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    if len(points) < 40:
        return None, {'version': VERSION, 'reason': 'insufficient_pan_points'}
    # Voxelisation removes view-density bias without inventing unseen points.
    _, ids = np.unique(np.floor(points / .003).astype(int), axis=0, return_index=True)
    cloud = points[np.sort(ids)]
    centre = np.median(cloud[:, :2], axis=0)
    _, axes = np.linalg.eigh(np.cov(cloud[:, :2].T))
    candidates, rejected = [], []
    for axis_index in (0, 1):
        along, across = axes[:, axis_index], axes[:, 1-axis_index]
        local = (cloud[:, :2] - centre) @ np.c_[along, across]
        # The round body's radius is measured along the perpendicular axis;
        # scan the longitudinal extension, rather than a fixed tail percentile.
        radius = float((np.quantile(local[:, 1], .99) - np.quantile(local[:, 1], .01)) / 2)
        for sign in (-1, 1):
            extension = cloud[(sign * local[:, 0] > radius + .006)
                              & (abs(local[:, 1]) < min(.035, radius * .45))]
            if len(extension) < 12:
                rejected.append({'axis': axis_index, 'sign': sign, 'reason': 'extension_not_visible'})
                continue
            pairs = cKDTree(extension).query_pairs(.010, output_type='ndarray')
            graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                               shape=(len(extension), len(extension)))
            count, labels = connected_components(graph, directed=False)
            for label in range(count):
                patch = extension[labels == label]
                if len(patch) < 12:
                    continue
                projection = (patch[:, :2] - centre) @ np.c_[along, across]
                length, width = np.diff(np.quantile(projection, (.02, .98), axis=0), axis=0)[0]
                reason = ('extension_too_short' if length < .02 else
                          'extension_not_slender' if length < width * 1.5 else
                          'handle_too_wide' if width >= .072 else None)
                detail = {'axis': axis_index, 'sign': sign, 'points': len(patch),
                          'length_m': float(length), 'width_m': float(width), 'body_radius_m': radius}
                if reason:
                    rejected.append({**detail, 'reason': reason})
                else:
                    candidates.append((float(length / max(width, .003)), patch, across, detail))
    if not candidates:
        return None, {'version': VERSION, 'reason': 'pan_handle_not_measured', 'rejected': rejected}
    _, patch, closure, detail = max(candidates, key=lambda c: c[0])
    return {'points': patch, 'centre_xy': np.median(patch[:, :2], axis=0), 'closing_axis_xy': closure}, {
        'version': VERSION, 'source': 'perception', 'method': 'connected_slender_axis_extension',
        'selected': detail, 'rejected': rejected, 'private_pose_used': False}
