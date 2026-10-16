"""Track measured moving payload surfaces without a spatial obstacle carve."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def _surface_translation(predicted, measured):
    """Refine EEF rigid motion by a bounded measured surface translation.

    Grip compliance can move an object a few millimetres relative to the
    fingers. Fit only the current clean instance, retaining the measured EEF
    rotation. A distant/weak fit supplies no correction.
    """
    def voxel(points):
        points = np.asarray(points, float).reshape(-1, 3)
        points = points[np.isfinite(points).all(axis=1)]
        _, ids = np.unique(np.floor(points/.001).astype(int), axis=0, return_index=True)
        return points[np.sort(ids)]
    source, target = voxel(predicted), voxel(measured)
    evidence = {'source': 'current_clean_rgbd_instance_surface', 'accepted': False,
                'translation_m': [0., 0., 0.], 'max_translation_m': .015}
    if min(len(source), len(target)) < 40:
        return np.zeros(3), evidence
    source = source[::max(1, len(source)//8000)]
    tree, shift = cKDTree(target), np.zeros(3)
    before = tree.query(source)[0]
    for _ in range(16):
        distance, ids = tree.query(source+shift)
        supported = distance <= .008
        if supported.sum() < 40 or supported.mean() < .5:
            return np.zeros(3), {**evidence, 'reason': 'surface_overlap_insufficient'}
        delta = np.median(target[ids[supported]]-(source+shift)[supported], axis=0)
        shift += delta
        if np.linalg.norm(shift) > .015:
            return np.zeros(3), {**evidence, 'reason': 'surface_shift_exceeds_public_hold_tolerance'}
        if np.linalg.norm(delta) < .00001:
            break
    after = tree.query(source+shift)[0]
    if np.median(after) >= np.median(before):
        return np.zeros(3), {**evidence, 'reason': 'surface_fit_not_improved'}
    return shift, {**evidence, 'accepted': True, 'translation_m': shift.tolist(),
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
    evidence = {'version': 'public-rigid-payload-membership/2-dev',
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
        correction, fit = _surface_translation(moved_target, current_target)
        moved_target += correction
        evidence['surface_registration'] = fit
    valid = np.isfinite(points).all(axis=1)
    eligible = (valid & (points >= moved_target.min(0)-surface_residual_m).all(axis=1)
                & (points <= moved_target.max(0)+surface_residual_m).all(axis=1))
    ids = np.flatnonzero(eligible)
    if not len(ids):
        return matched, evidence
    supported = cKDTree(moved_target).query(points[ids])[0] <= surface_residual_m
    ids = ids[supported]
    evidence['candidate_points'] = len(ids)
    if len(ids):
        stationary = cKDTree(reference['scene']).query(points[ids])[0] <= stationary_residual_m
        matched[ids[~stationary]] = True
        evidence['stationary_points_retained'] = int(stationary.sum())
        evidence['associated_points'] = int((~stationary).sum())
    return matched, evidence
