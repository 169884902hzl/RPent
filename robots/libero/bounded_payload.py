"""Track measured moving payload surfaces without a spatial obstacle carve."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def complete_moving_boundary(world, mask, moving_points, stationary_points, *, surface_extent=None):
    """Extend current RGB-D surfaces from independently co-moving edge pixels.

    Temporal association can recover a previously omitted silhouette pixel.
    Use the two interior pixels' measured tangent spacing and a 1 mm
    extrapolation residual, including at grazing surfaces. Do not widen the
    4 mm temporal association radius. Old stationary pixels are retained
    after every extension, so they cannot become new seeds. With a measured
    moving-surface extent, continue to convergence inside that extent instead
    of treating three image pixels as a physical distance.
    """
    from robots.libero.v5_grasp_geometry import (
        complete_instance_boundary,
        complete_planar_boundary,
    )

    world, mask = np.asarray(world), np.asarray(mask, bool)
    moving = np.asarray(moving_points, float).reshape(-1, 3)
    evidence = {'version': 'public-temporal-seeded-instance-boundary/4-dev',
        'source': 'co_moving_public_pixels_and_same_view_rgbd_continuity',
        'spacing_source': 'measured_two_pixel_tangent',
        'max_extrapolation_error_m': .001,
        'temporal_seed_pixels': 0, 'added_pixels': 0, 'stationary_points_retained': 0}
    if not len(moving):
        return mask.copy(), evidence
    flat = world.reshape(-1, 3)
    eligible = (np.isfinite(flat).all(axis=1)
        & (flat >= moving.min(0)-1e-6).all(axis=1)
        & (flat <= moving.max(0)+1e-6).all(axis=1))
    ids = np.flatnonzero(eligible)
    owned = ids[cKDTree(moving).query(flat[ids],
        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6]
    current = mask.copy()
    current.flat[owned] = True
    evidence['temporal_seed_pixels'] = int((current & ~mask).sum())
    static = cKDTree(stationary_points)
    bounded_world = world
    if surface_extent is not None:
        lower, upper = np.asarray(surface_extent)
        eligible = ((world >= lower).all(axis=2) & (world <= upper).all(axis=2)) | current
        bounded_world = world.copy()
        bounded_world[~eligible] = np.nan
        evidence['measured_surface_extent_m'] = [lower.tolist(), upper.tolist()]
    retained = np.zeros(mask.shape, bool)
    def keep_stationary(extended):
        new = np.flatnonzero(extended & ~current)
        stationary = static.query(flat[new],
            distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
        retained.flat[new[stationary]] = True
        extended.flat[new[stationary]] = False
        return extended
    rounds, planar_rounds = [], []
    for _ in range(sum(mask.shape) if surface_extent is not None else 3):
        extended, _ = complete_instance_boundary(bounded_world, current, rounds=1,
            measured_tangent_spacing=True)
        extended = keep_stationary(extended)
        directional_added = int((extended & ~current).sum())
        current = extended
        # A measured plane can recover the two missing interior pixels that
        # seed the next tangent extension. Include that stage in convergence;
        # a final plane pass alone left its newly supported edge as an obstacle.
        if not directional_added:
            extended, _ = complete_planar_boundary(bounded_world, current)
            extended = keep_stationary(extended)
            planar_added = int((extended & ~current).sum())
            current = extended
        else:
            planar_added = 0
        rounds.append(directional_added+planar_added)
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
    return current, evidence


def _surface_registration(predicted, measured):
    """Refine EEF motion by a bounded rigid fit of the measured surface.

    Grip compliance can translate and tilt an object relative to the fingers.
    Fit only the current clean instance; a distant/weak fit supplies no
    correction. Bound the displacement of every predicted point, including
    those outside the matched patch, rather than just the fitted centroid.
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
        if angle > .1 or displacement.max() > .015:
            return predicted, {**evidence, 'reason': 'surface_shift_exceeds_public_hold_tolerance'}
        change = (a-ac)@delta_rotation.T+bc-a
        if np.linalg.norm(change, axis=1).max() < .00001:
            break
    after = tree.query((source-centre)@rotation.T+centre+shift)[0]
    if np.median(after) >= np.median(before):
        return predicted, {**evidence, 'reason': 'surface_fit_not_improved'}
    return corrected, {**evidence, 'accepted': True, 'translation_m': shift.tolist(),
        'rotation_rad': angle, 'rotation_matrix': rotation.tolist(),
        'maximum_surface_displacement_m': float(displacement.max()),
        'median_residual_before_m': float(np.median(before)),
        'median_residual_after_m': float(np.median(after)), 'samples': len(source)}


def moving_payload_pixels(points, reference, robot, *, current_target=None, surface_residual_m=.004,
                          stationary_residual_m=.004):
    """Associate only measured co-moving points absent from the stationary scene.

    ``reference`` is the public RGB-D capture immediately before a verified
    lift. EEF poses come from proprioception. A nearby static obstacle wins
    over a moving-target match, including at a segmentation boundary. No
    object simulator pose, RGB category rule or bounding-box carve is used.
    """
    points = np.asarray(points, float).reshape(-1, 3)
    reference_robot = reference['robot']
    rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
    old_rotation = Rotation.from_quat(reference_robot['eef_quat_xyzw']).as_matrix()
    old_target = np.asarray(reference['target'], float).reshape(-1, 3)
    evidence = {'version': 'public-rigid-payload-membership/3-dev',
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
    evidence['measured_surface_extent_m'] = [
        (moved_target.min(0)-surface_residual_m).tolist(),
        (moved_target.max(0)+surface_residual_m).tolist()]
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
