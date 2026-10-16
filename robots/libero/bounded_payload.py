"""Track measured moving payload surfaces without a spatial obstacle carve."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


def moving_payload_pixels(points, reference, robot, *, surface_residual_m=.004,
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
    evidence = {'version': 'public-rigid-payload-membership/1-dev',
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
