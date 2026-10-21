# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Track measured moving payload surfaces without a spatial obstacle carve."""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def _inside_bounds(points, lower, upper):
    """Inclusive XYZ bounds without per-pixel three-channel reductions."""
    return ((points[..., 0] >= lower[0]) & (points[..., 0] <= upper[0])
            & (points[..., 1] >= lower[1]) & (points[..., 1] <= upper[1])
            & (points[..., 2] >= lower[2]) & (points[..., 2] <= upper[2]))


def complete_spatial_payload_component(points, seeds, stationary_points, lower, upper):
    """Associate current raw depth components inside measured payload bounds.

    Keep exact pixel-to-pixel edges at the existing 3 mm depth gap. A voxel
    representative can be farther away than another pixel in that same
    voxel and falsely disconnect a visible surface across camera views.
    Pre-lift static pixels are removed before constructing any connections.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    points, seeds, stationary = (np.asarray(p, float).reshape(-1, 3)
                                  for p in (points, seeds, stationary_points))
    member = np.zeros(len(points), bool)
    evidence = {'source': 'raw_current_rgbd_components_inside_measured_payload_bounds',
        'max_gap_m': .003, 'stationary_residual_m': .004,
        'private_pose_used': False, 'eligible_points': 0, 'seed_pixels': 0,
        'stationary_points_retained': 0, 'exact_edges': 0, 'member_pixels': 0}
    ids = np.flatnonzero(np.isfinite(points).all(axis=1)
        & (points >= lower).all(axis=1) & (points <= upper).all(axis=1))
    seeds = seeds[np.isfinite(seeds).all(axis=1)]
    stationary = stationary[np.isfinite(stationary).all(axis=1)]
    if len(stationary) and len(ids):
        static = cKDTree(stationary).query(points[ids],
            distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
        evidence['stationary_points_retained'] = int(static.sum())
        ids = ids[~static]
    evidence['eligible_points'] = len(ids)
    if not len(ids) or not len(seeds):
        return member, evidence
    current = points[ids]
    seed = cKDTree(seeds).query(current,
        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
    evidence['seed_pixels'] = int(seed.sum())
    if not seed.any():
        return member, evidence
    tree = cKDTree(current)
    # Only membership in ANY seeded component matters. Contract all seeded
    # vertices to one root; edges between seeds cannot change that answer.
    # Dense surfaces often already have >99% seeds, so constructing all
    # seed-to-seed edges wastes most of the memory and graph work.
    unknown = np.flatnonzero(~seed)
    pairs = cKDTree(current[unknown]).query_pairs(.003, output_type='ndarray')
    touches_seed = cKDTree(current[seed]).query(current[unknown])[0] <= .003
    root = len(unknown)
    direct = np.flatnonzero(touches_seed)
    left = np.r_[pairs[:, 0], direct]
    right = np.r_[pairs[:, 1], np.full(len(direct), root)]
    graph = coo_matrix((np.ones(len(left), np.uint8), (left, right)),
                      shape=(root+1, root+1)).tocsr()
    _, labels = connected_components(graph, directed=False)
    member[ids[seed]] = True
    member[ids[unknown]] = labels[:root] == labels[root]
    # Keep the original exact-edge diagnostic without materializing those
    # edges. The self query includes each diagonal and both directions.
    evidence['exact_edges'] = (int(tree.count_neighbors(tree, .003))-len(current))//2
    evidence['member_pixels'] = int(member.sum())
    return member, evidence


def complete_moving_boundary(world, mask, moving_points, stationary_points, *, surface_extent=None,
                             rgb=None, semantic_mask=None):
    """Extend current RGB-D surfaces from independently co-moving edge pixels.

    Temporal association can recover a previously omitted silhouette pixel.
    Use the two interior pixels' measured tangent spacing and a 1 mm
    extrapolation residual, including at grazing surfaces. Do not widen the
    4 mm temporal association radius. Old stationary pixels are retained
    after every extension, so they cannot become new seeds. With a measured
    moving-surface extent, continue to convergence inside that extent instead
    of treating three image pixels as a physical distance. When RGB is
    available, each silhouette ring also needs local appearance/depth support
    and the same moving-extent/static-scene constraints. Current depth
    components can cross an object's colour boundary and the transported
    extent when supported by connected current depth. They still stop at
    the existing 3 mm depth gap, robot filtering and static-scene veto.
    Current semantic edge pixels outside that extent require the same
    two-pixel RGB/depth support; the semantic mask alone never owns them.
    Newly owned current depth pixels enlarge the association extent before
    the next boundary pass. A transported extent cannot hide current samples
    that have already passed the same depth and stationary-scene checks.
    """
    from robots.libero.v5_grasp_geometry import (
        complete_instance_boundary,
        complete_planar_boundary,
    )

    world, mask = np.asarray(world), np.asarray(mask, bool)
    moving = np.asarray(moving_points, float).reshape(-1, 3)
    evidence = {'version': 'public-temporal-seeded-instance-boundary/11-dev',
        'source': 'co_moving_public_pixels_and_same_view_rgbd_continuity',
        'spacing_source': 'measured_two_pixel_tangent',
        'max_extrapolation_error_m': .001,
        'temporal_seed_pixels': 0, 'added_pixels': 0, 'stationary_points_retained': 0}
    if not len(moving):
        return mask.copy(), evidence
    flat = world.reshape(-1, 3)
    eligible = (np.isfinite(flat).all(axis=1)
        & _inside_bounds(flat, moving.min(0)-1e-6, moving.max(0)+1e-6))
    ids = np.flatnonzero(eligible)
    owned = ids[cKDTree(moving).query(flat[ids],
        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6]
    current = mask.copy()
    current.flat[owned] = True
    evidence['temporal_seed_pixels'] = int((current & ~mask).sum())
    static = cKDTree(stationary_points)
    # Static evidence also outranks the initial semantic mask. Otherwise a
    # mask bleeding onto a basket/plate keeps that surface as payload even
    # though every newly added pixel is correctly vetoed below.
    initial_ids = np.flatnonzero(current)
    initial_stationary = static.query(flat[initial_ids],
        distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
    current.flat[initial_ids[initial_stationary]] = False
    evidence['initial_mask_stationary_pixels_retained'] = int(initial_stationary.sum())
    bounded_world = world
    if surface_extent is not None:
        lower, upper = np.asarray(surface_extent)
        eligible = _inside_bounds(world, lower, upper) | current
        bounded_world = world.copy()
        bounded_world[~eligible] = np.nan
        evidence['measured_surface_extent_m'] = [lower.tolist(), upper.tolist()]
    original_extent_valid = np.isfinite(bounded_world).all(axis=2)
    retained = np.zeros(mask.shape, bool)
    def keep_stationary(extended):
        new = np.flatnonzero(extended & ~current)
        stationary = static.query(flat[new],
            distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
        retained.flat[new[stationary]] = True
        extended.flat[new[stationary]] = False
        if appearance:
            # Growing the measured envelope must retain the existing RGB-D
            # support rule for pixels outside the original association
            # extent; a geometric pass cannot bypass an appearance conflict.
            for index in new[~stationary & ~original_extent_valid.flat[new]]:
                y, x = np.unravel_index(index, mask.shape)
                ys, xs = slice(max(0, y-2), y+3), slice(max(0, x-2), x+3)
                local = current[ys, xs]
                colour = np.max(np.abs(image[ys, xs][local]-image[y, x]), axis=1)
                distance = np.linalg.norm(world[ys, xs][local]-world[y, x], axis=1)
                if ((colour <= .1) & (distance <= .025)).sum() < 2:
                    extended[y, x] = False
        return extended
    appearance = rgb is not None and surface_extent is not None
    appearance_rounds = []
    semantic_edge_pixels = 0
    if appearance:
        from scipy.ndimage import binary_dilation

        # A curved silhouette can jump by centimetres between adjacent
        # pixels, so two-pixel linear extrapolation need not fit it. Each
        # image ring needs appearance AND depth support inside the co-moving
        # extent or the current semantic edge. Static neighbours still win.
        image = np.asarray(rgb, float)/255.
        appearance_valid = np.isfinite(bounded_world).all(axis=2)
        if semantic_mask is not None:
            appearance_valid |= np.asarray(semantic_mask, bool) & np.isfinite(world).all(axis=2)
    def appearance_ring():
        nonlocal semantic_edge_pixels
        extended = current.copy()
        ring = binary_dilation(current) & ~current & appearance_valid
        for y, x in zip(*np.nonzero(ring)):
            ys, xs = slice(max(0, y-2), y+3), slice(max(0, x-2), x+3)
            local = current[ys, xs]
            colour = np.max(np.abs(image[ys, xs][local]-image[y, x]), axis=1)
            distance = np.linalg.norm(world[ys, xs][local]-world[y, x], axis=1)
            if ((colour <= .1) & (distance <= .025)).sum() >= 2:
                extended[y, x] = True
        extended = keep_stationary(extended)
        semantic_edge_pixels += int((extended & ~current & ~np.isfinite(bounded_world).all(axis=2)).sum())
        appearance_rounds.append(int((extended & ~current).sum()))
        return extended
    if appearance:
        current = appearance_ring()
    labels = None
    if surface_extent is not None:
        from robots.libero.v5_grasp_geometry import depth_components

        valid = np.isfinite(world).all(axis=2)
        ids = np.flatnonzero(valid)
        stationary = static.query(flat[ids],
            distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
        valid.flat[ids[stationary]] = False
        labels, _ = depth_components(world, valid, max_gap_m=.003)
        evidence['depth_connected_current_surface_pixels'] = 0
        evidence['depth_component_scope'] = 'current_self_filtered_rgbd_without_pre_lift_static_pixels'
    rounds, planar_rounds = [], []
    for _ in range(sum(mask.shape) if surface_extent is not None else 3):
        if surface_extent is not None and current.any():
            measured = world[current]
            next_lower = np.minimum(lower, measured.min(axis=0))
            next_upper = np.maximum(upper, measured.max(axis=0))
            if np.any(next_lower < lower) or np.any(next_upper > upper):
                lower, upper = next_lower, next_upper
                bounded_world = world.copy()
                eligible = _inside_bounds(world, lower, upper) | current
                bounded_world[~eligible] = np.nan
                evidence['measured_surface_extent_m'] = [lower.tolist(), upper.tolist()]
                if appearance:
                    appearance_valid = np.isfinite(bounded_world).all(axis=2)
                    if semantic_mask is not None:
                        appearance_valid |= np.asarray(semantic_mask, bool) & np.isfinite(world).all(axis=2)
        extended, _ = complete_instance_boundary(bounded_world, current, rounds=1,
            measured_tangent_spacing=True)
        # Extent-limited geometric helpers omit semantic edge pixels outside
        # their input cloud. Retain already supported membership, or each
        # appearance pass re-adds those same pixels without convergence.
        extended |= current
        extended = keep_stationary(extended)
        directional_added = int((extended & ~current).sum())
        current = extended
        # A measured plane can recover the two missing interior pixels that
        # seed the next tangent extension. Include that stage in convergence;
        # a final plane pass alone left its newly supported edge as an obstacle.
        if not directional_added:
            extended, _ = complete_planar_boundary(bounded_world, current,
                measured_tangent_spacing=surface_extent is not None)
            extended |= current
            extended = keep_stationary(extended)
            planar_added = int((extended & ~current).sum())
            current = extended
        else:
            planar_added = 0
        appearance_added = 0
        if not directional_added and not planar_added and appearance:
            extended = appearance_ring()
            appearance_added = int((extended & ~current).sum())
            current = extended
        connected_added = 0
        if not directional_added and not planar_added and not appearance_added and labels is not None:
            # Newly connected depth pixels can supply the second measured
            # support for a curved silhouette. Resume the same boundary
            # checks instead of stopping before those supports are used.
            supported = np.unique(labels[current & valid])
            connected = (labels >= 0) & np.isin(labels, supported)
            connected_added = int((connected & ~current).sum())
            current |= connected
            evidence['depth_connected_current_surface_pixels'] += connected_added
        rounds.append(directional_added+planar_added+appearance_added+connected_added)
        planar_rounds.append(planar_added)
        if rounds[-1] == 0:
            break
    if surface_extent is None:
        # Preserve the final local-plane ring for the bounded three-round
        # path; only a measured extent authorises iterative completion.
        extended, _ = complete_planar_boundary(bounded_world, current)
        current = keep_stationary(extended)
    evidence['added_pixels_per_round'] = rounds
    evidence['planar_added_pixels_per_round'] = planar_rounds
    evidence['added_pixels'] = int((current & ~mask).sum())
    evidence['stationary_points_retained'] = int(retained.sum())
    if appearance:
        evidence['appearance_boundary'] = {'version': 'public-rgbd-silhouette-ring/3-dev',
            'stop': 'no_further_supported_pixels_in_extent_or_current_semantic_edge',
            'max_channel_difference': .1, 'max_pixel_surface_step_m': .025,
            'minimum_support_pixels': 2, 'added_pixels': sum(appearance_rounds),
            'current_semantic_edge_pixels_outside_predicted_extent': semantic_edge_pixels,
            'added_pixels_per_round': appearance_rounds}
    return current, evidence


def _surface_registration(predicted, measured, *, reciprocal=False):
    """Refine EEF motion by a bounded rigid fit of the measured surface.

    Grip compliance can translate and tilt an object relative to the fingers.
    Pre-lift fits may restrict matches to mutually nearest surface pairs
    so an occluded reference cannot rotate toward the visible silhouette.
    Held-payload fits retain their motion-predicted correspondences. A
    distant/weak fit supplies no correction. Bound every predicted point,
    including those outside the patch, rather than just its centroid.
    """
    def voxel(points):
        points = np.asarray(points, float).reshape(-1, 3)
        points = points[np.isfinite(points).all(axis=1)]
        _, ids = np.unique(np.floor(points/.001).astype(int), axis=0, return_index=True)
        return points[np.sort(ids)]
    source, target = voxel(predicted), voxel(measured)
    predicted = np.asarray(predicted, float).reshape(-1, 3)
    evidence = {'source': 'current_clean_rgbd_instance_surface', 'accepted': False,
                'translation_m': [0., 0., 0.], 'rotation_rad': 0.,
                'max_surface_displacement_m': .015, 'max_rotation_rad': .1}
    if min(len(source), len(target)) < 40:
        return predicted, evidence
    source = source[::max(1, len(source)//8000)]
    tree = cKDTree(target)
    centre = source.mean(axis=0)
    rotation, shift = np.eye(3), np.zeros(3)
    before = tree.query(source)[0]
    for _ in range(30):
        transformed = (source-centre)@rotation.T+centre+shift
        distance, ids = tree.query(transformed)
        supported = distance <= .008
        if supported.sum() < 40 or supported.mean() < .5:
            return predicted, {**evidence, 'reason': 'surface_overlap_insufficient'}
        # One-sided ICP maps hidden parts of the old surface to a visible
        # silhouette and can invent rotation under finger occlusion. Keep
        # the original overlap gate, but fit only reciprocal pairs.
        if reciprocal:
            reverse = cKDTree(transformed).query(target[ids])[1]
            supported &= reverse == np.arange(len(source))
            if supported.sum() < 40:
                return predicted, {**evidence, 'reason': 'reciprocal_surface_correspondences_missing'}
        a, b = transformed[supported], target[ids[supported]]
        ac, bc = a.mean(axis=0), b.mean(axis=0)
        u, _, vt = np.linalg.svd((a-ac).T@(b-bc))
        delta_rotation = vt.T@u.T
        if np.linalg.det(delta_rotation) < 0:
            vt[-1] *= -1
            delta_rotation = vt.T@u.T
        delta = bc-ac@delta_rotation.T
        shift = (centre+shift)@delta_rotation.T+delta-centre
        rotation = delta_rotation@rotation
        corrected = (predicted-centre)@rotation.T+centre+shift
        displacement = np.linalg.norm(corrected-predicted, axis=1)
        angle = float(Rotation.from_matrix(rotation).magnitude())
        change = (a-ac)@delta_rotation.T+bc-a
        if np.linalg.norm(change, axis=1).max() < .00001:
            break
    # ICP iterates are optimization proposals, not accepted scene motion.
    # A partial curved view can temporarily overshoot before its final fit
    # returns inside these same bounds. Only the returned transform grants
    # membership; keep the original prediction if that final fit is invalid.
    if angle > .1 or displacement.max() > .015:
        return predicted, {**evidence, 'reason': 'surface_shift_exceeds_public_hold_tolerance'}
    after = tree.query((source-centre)@rotation.T+centre+shift)[0]
    if np.median(after) >= np.median(before):
        return predicted, {**evidence, 'reason': 'surface_fit_not_improved'}
    return corrected, {**evidence, 'accepted': True, 'translation_m': shift.tolist(),
        'rotation_rad': angle, 'rotation_matrix': rotation.tolist(),
        'maximum_surface_displacement_m': float(displacement.max()),
        'median_residual_before_m': float(np.median(before)),
        'median_residual_after_m': float(np.median(after)), 'samples': len(source),
        **({'correspondences': 'mutual_nearest_surface_pixels',
            'reciprocal_pairs': int(supported.sum())} if reciprocal else {})}


def contact_axis_registration(reference, current_scene, axis, distance_m, *, endpoint_tolerance_m=.012,
                              query_workers=1, coarse_to_fine=True):
    """Measure a bounded translation without reusing a changing SAM centre.

    Fit the pre-contact surface to current self-filtered public depth along
    both signs of the selected axis. Missing surface points have a capped
    residual. Fits within an additional (1 mm)^2 mean squared residual are
    retained: a flat/occluded surface must not invent a unique displacement.
    This compatible range is a geometric ambiguity check, not a confidence
    interval. No EEF displacement or private object pose drives the fit.
    """
    source = np.asarray(reference, float).reshape(-1, 3)
    target = np.asarray(current_scene, float).reshape(-1, 3)
    source = source[np.isfinite(source).all(axis=1)]
    target = target[np.isfinite(target).all(axis=1)]
    evidence = {'source': 'pre_action_surface_and_current_self_filtered_rgbd',
        'accepted': False, 'translation_m': None, 'compatible_axis_interval_m': None,
        'residual_cap_m': .008, 'squared_residual_increment_m2': .001**2, 'private_pose_used': False}
    if min(len(source), len(target)) < 40:
        return {**evidence, 'reason': 'contact_surface_samples_missing'}
    _, ids = np.unique(np.floor(source/.001).astype(int), axis=0, return_index=True)
    source = source[np.sort(ids)]
    source = source[::max(1, math.ceil(len(source)/6000))]
    if len(source) < 40:
        return {**evidence, 'reason': 'contact_surface_samples_missing'}
    radius = abs(distance_m)+endpoint_tolerance_m
    lo, hi = source.min(0)-radius, source.max(0)+radius
    target = target[((target >= lo) & (target <= hi)).all(axis=1)]
    if len(target) < 40:
        return {**evidence, 'reason': 'current_contact_surface_missing'}
    tree = cKDTree(target)
    shifts = np.linspace(-radius, radius, 2*math.ceil(radius/.001)+1)
    # Query shifts in bounded batches. Every source row and shift retains
    # its original order, cap and reduction; only independent NN queries
    # share a call, without numerical approximation or learned geometry.
    scores, supported = np.full(len(shifts), np.inf), np.zeros(len(shifts))
    evaluated = np.zeros(len(shifts), bool)
    def evaluate(indices):
        for start in range(0, len(indices), 8):
            ids = np.asarray(indices[start:start+8], dtype=int)
            offsets = np.zeros((len(ids), 3))
            offsets[:, axis] = shifts[ids]
            residual = tree.query((source[None, :, :]+offsets[:, None, :]).reshape(-1, 3),
                workers=query_workers, distance_upper_bound=np.nextafter(.008, np.inf)
                )[0].reshape(len(ids), len(source))
            scores[ids] = np.mean(np.minimum(residual, .008)**2, axis=1)
            supported[ids] = np.mean(residual <= .008, axis=1)
            evaluated[ids] = True
    if coarse_to_fine:
        # First <=8 mm grid, then 1 mm around its best fit. The truncated
        # nearest-surface RMS objective is 1-Lipschitz in translation. This
        # gives a certified lower bound for every remaining fine-grid point;
        # uncertain secondary minima/ambiguous flat surfaces are still tested.
        coarse = np.unique(np.r_[np.arange(0,len(shifts),8),len(shifts)-1])
        evaluate(coarse)
        centre = shifts[np.argmin(scores)]
        evaluate(np.flatnonzero(~evaluated & (np.abs(shifts-centre) <= .008)))
        remaining = np.flatnonzero(~evaluated)
        if len(remaining):
            known = np.flatnonzero(evaluated)
            bounds = np.maximum(0., np.sqrt(scores[known, None])
                -np.abs(shifts[known, None]-shifts[remaining]))
            lower = bounds.max(axis=0)**2
            evaluate(remaining[lower <= scores.min()+.001**2+1e-14])
    else:
        evaluate(np.arange(len(shifts)))
    best = int(np.argmin(scores))
    compatible = shifts[np.asarray(scores) <= scores[best]+.001**2]
    translation = np.zeros(3)
    translation[axis] = shifts[best]
    evidence.update(translation_m=translation.tolist(),
        # Millimetre-grid arithmetic can put a nominal 5mm bound a few
        # ulps below the 5mm progress gate. Picometre serialization removes
        # that arithmetic noise without changing the measured threshold.
        compatible_axis_interval_m=np.round([compatible.min(), compatible.max()], 12).tolist(),
        mean_capped_squared_residual_m2=scores[best], supported_fraction=supported[best],
        samples=len(source), fits=len(shifts))
    if supported[best] < .5:
        return {**evidence, 'reason': 'contact_surface_overlap_insufficient'}
    if best in {0, len(shifts)-1}:
        return {**evidence, 'reason': 'contact_surface_shift_at_search_boundary'}
    return {**evidence, 'accepted': True, 'reason': 'public_axis_surface_fit'}


def stationary_surface_registration(reference, current_scene, current_instance, *, tolerance_m=.01,
                                    query_workers=1):
    """Recheck a shifted visible centre against its unchanged measured surface.

    Shared current instance pixels establish identity. Three bounded axis
    fits must each constrain displacement; a flat ambiguous patch cannot
    authorize continuation merely because it overlaps a stationary plane.
    This supplies no corrected pose and never moves an old grasp point.
    """
    source, instance = (np.asarray(points, float).reshape(-1, 3)
                        for points in (reference, current_instance))
    source = source[np.isfinite(source).all(axis=1)]
    instance = instance[np.isfinite(instance).all(axis=1)]
    result = {'source': 'pre_action_surface_and_current_public_rgbd', 'accepted': False,
              'private_pose_used': False, 'tolerance_m': tolerance_m, 'axis_fits': {}}
    if min(len(source), len(instance)) < 40:
        return {**result, 'reason': 'instance_surface_missing'}
    overlap = cKDTree(source).query(instance, workers=query_workers,
        distance_upper_bound=np.nextafter(.001, np.inf))[0] <= .001
    result['shared_instance_pixels'] = int(overlap.sum())
    if overlap.sum() < 40:
        return {**result, 'reason': 'current_instance_identity_not_shared'}
    bounds = []
    for axis in range(3):
        fit = contact_axis_registration(source, current_scene, axis, .02, query_workers=query_workers)
        result['axis_fits']['xyz'[axis]] = fit
        if not fit['accepted']:
            return {**result, 'reason': 'surface_displacement_unmeasured'}
        bounds.append(max(abs(v) for v in fit['compatible_axis_interval_m']))
    bound = float(np.linalg.norm(bounds))
    result['compatible_displacement_bound_m'] = bound
    accepted = bound <= tolerance_m
    return {**result, 'accepted': accepted,
            'reason': 'surface_still_at_measured_anchor' if accepted else 'surface_moved_or_ambiguous'}


def contact_normal_registration(predicted, measured, normal):
    """Fit contact compliance along a publicly measured surface normal.

    An occluded bar's unconstrained rigid fit can drift along its tangent.
    This fit cannot rotate the old surface or move it along that tangent.
    The existing 15 mm displacement and 8 mm/half-surface overlap limits
    still apply; only a lower current-depth median residual is accepted.
    """
    from scipy.optimize import minimize_scalar

    predicted = np.asarray(predicted, float).reshape(-1, 3)
    measured = np.asarray(measured, float).reshape(-1, 3)
    normal = np.asarray(normal, float)
    evidence = {'source': 'current_self_filtered_rgbd_and_measured_contact_normal',
        'accepted': False, 'translation_m': [0., 0., 0.], 'rotation_rad': 0.,
        'max_surface_displacement_m': .015, 'private_pose_used': False}
    if (min(len(predicted), len(measured)) < 40 or normal.shape != (3,)
            or not np.isfinite(normal).all() or np.linalg.norm(normal) < 1e-6):
        return predicted, {**evidence, 'reason': 'contact_fit_inputs_missing'}
    normal = normal/np.linalg.norm(normal)
    _, ids = np.unique(np.floor(predicted/.001).astype(int), axis=0, return_index=True)
    source = predicted[ids]
    tree = cKDTree(measured)
    def residual(shift):
        return tree.query(source+normal*shift)[0]
    before = residual(0.)
    if (before <= .008).sum() < 40 or (before <= .008).mean() < .5:
        return predicted, {**evidence, 'reason': 'surface_overlap_insufficient'}
    fit = minimize_scalar(lambda shift: float(np.mean(np.minimum(residual(shift), .004)**2)),
        bounds=(-.015, .015), method='bounded', options={'xatol': 1e-6})
    after = residual(fit.x)
    if (not fit.success or (after <= .008).sum() < 40 or (after <= .008).mean() < .5
            or np.median(after) >= np.median(before)):
        return predicted, {**evidence, 'reason': 'surface_fit_not_improved'}
    shift = normal*fit.x
    return predicted+shift, {**evidence, 'accepted': True, 'translation_m': shift.tolist(),
        'normal_xyz': normal.tolist(), 'samples': len(source),
        'median_residual_before_m': float(np.median(before)),
        'median_residual_after_m': float(np.median(after))}


def moving_payload_pixels(points, reference, robot, *, current_target=None, current_semantic_target=None,
                          surface_residual_m=.004,
                          stationary_residual_m=.004):
    """Associate only measured co-moving points absent from the stationary scene.

    ``reference`` is the public RGB-D capture immediately before a verified
    lift. EEF poses come from proprioception. A nearby static obstacle wins
    over a moving-target match, including at a segmentation boundary. No
    object simulator pose, RGB category rule or bounding-box carve is used.
    When a global fit is rejected, current semantic pixels still require
    independent clean-surface support and a stricter temporal match; they
    cannot reinstate the rejected transform or its predicted extent.
    """
    points = np.asarray(points, float).reshape(-1, 3)
    reference_robot = reference['robot']
    rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
    old_rotation = Rotation.from_quat(reference_robot['eef_quat_xyzw']).as_matrix()
    old_target = np.asarray(reference['target'], float).reshape(-1, 3)
    evidence = {'version': 'public-rigid-payload-membership/5-dev',
        'source': 'pre_lift_rgbd_target_and_scene_with_measured_eef_motion',
        'reference_capture_step': reference['capture_step'],
        'surface_residual_m': surface_residual_m,
        'stationary_residual_m': stationary_residual_m,
        'candidate_points': 0, 'stationary_points_retained': 0,
        'associated_points': 0, 'private_pose_used': False}
    matched = np.zeros(len(points), bool)
    if not len(old_target) or not len(reference['scene']):
        return matched, evidence
    moved_target = ((old_target-reference_robot['eef_xyz_m'])@old_rotation)@rotation.T+robot['eef_xyz_m']
    if current_target is not None:
        moved_target, fit = _surface_registration(moved_target, current_target)
        evidence['surface_registration'] = fit
        partial_view = False
        if fit.get('reason') == 'surface_overlap_insufficient' and len(current_target) >= 40:
            # Most of the old surface can be occluded even when the current
            # visible patch agrees with its rigid motion. Check the reverse
            # overlap before treating incomplete visibility as contradiction.
            # This accepts no fitted transform: every owned current pixel
            # still needs the original residual and static-scene veto below.
            residual = cKDTree(moved_target).query(current_target)[0]
            support = float(np.mean(residual <= surface_residual_m))
            partial_view = support >= .9
            evidence['partial_view_support'] = {
                'current_points': len(current_target), 'supported_fraction': support,
                'minimum_fraction': .9, 'residual_m': surface_residual_m,
                'rigid_prediction_retained': partial_view}
        if (not fit['accepted'] and len(current_target) >= 40
                and fit.get('reason') in {'surface_shift_exceeds_public_hold_tolerance',
                                          'surface_overlap_insufficient'} and not partial_view):
            # Current depth contradicts the rigid prediction. Keep the
            # unaccepted prior out of ownership and extent, rather than
            # claiming a destination rim at the old predicted object edge.
            # The caller can still refine exact current-mask pixels by
            # image continuity; this adds no metric nearest-point carve.
            surface = np.asarray(current_target).reshape(-1, 3)
            evidence.update(temporal_prediction_rejected=True,
                measured_surface_extent_m=[(surface.min(0)-surface_residual_m).tolist(),
                                           (surface.max(0)+surface_residual_m).tolist()])
            if current_semantic_target is not None and len(current_semantic_target):
                # Reject the global transform, but do not discard a current
                # SAM fragment independently matching the old moving surface.
                # Require exact current semantic pixels, a stricter 1 mm
                # temporal match and an independently supported clean patch.
                prior = cKDTree(moved_target)
                clean_support = int((prior.query(surface)[0] <= surface_residual_m).sum())
                ids = np.flatnonzero(np.isfinite(points).all(axis=1))
                semantic = cKDTree(current_semantic_target).query(points[ids],
                    distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                consistent = prior.query(points[ids],
                    distance_upper_bound=np.nextafter(.001, np.inf))[0] <= .001
                static = cKDTree(reference['scene']).query(points[ids],
                    distance_upper_bound=np.nextafter(stationary_residual_m, np.inf))[0] <= stationary_residual_m
                if clean_support >= 40:
                    matched[ids[semantic & consistent & ~static]] = True
                evidence.update(candidate_points=int((semantic & consistent).sum()),
                    stationary_points_retained=int((semantic & consistent & static).sum()),
                    associated_points=int(matched.sum()))
                evidence['current_semantic_temporal_fragments'] = {
                    'clean_supported_points': clean_support, 'minimum_clean_supported_points': 40,
                    'temporal_residual_m': .001, 'exact_semantic_residual_m': 1e-6,
                    'associated_points': int(matched.sum()),
                    'stationary_semantic_matches_retained': int((semantic & consistent & static).sum())}
            return matched, evidence
    # Current instance pixels already form part of the payload. A compliant
    # grip can reveal a surface beyond the old rigid prediction even when a
    # partial-view registration cannot be accepted. Boundary refinement must
    # include this actually measured extent, with the same residual, rather
    # than truncating the surface at the old prediction's bounds.
    extent_points = moved_target
    if current_target is not None and len(current_target):
        extent_points = np.concatenate([moved_target, np.asarray(current_target).reshape(-1, 3)])
    evidence['measured_surface_extent_m'] = [
        (extent_points.min(0)-surface_residual_m).tolist(),
        (extent_points.max(0)+surface_residual_m).tolist()]
    valid = np.isfinite(points).all(axis=1)
    eligible = (valid & (points >= moved_target.min(0)-surface_residual_m).all(axis=1)
                & (points <= moved_target.max(0)+surface_residual_m).all(axis=1))
    ids = np.flatnonzero(eligible)
    if not len(ids):
        return matched, evidence
    supported = cKDTree(moved_target).query(points[ids],
        distance_upper_bound=np.nextafter(surface_residual_m, np.inf))[0] <= surface_residual_m
    ids = ids[supported]
    evidence['candidate_points'] = len(ids)
    if len(ids):
        stationary = cKDTree(reference['scene']).query(points[ids],
            distance_upper_bound=np.nextafter(stationary_residual_m, np.inf))[0] <= stationary_residual_m
        matched[ids[~stationary]] = True
        evidence['stationary_points_retained'] = int(stationary.sum())
        evidence['associated_points'] = int((~stationary).sum())
    return matched, evidence
