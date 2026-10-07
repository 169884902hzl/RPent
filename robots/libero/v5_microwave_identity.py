"""Public RGB-D correspondence diagnostic for an independently observed door.

This opt-in development path tracks an observed moving surface; it never
creates an identity from an appliance front plane or reads task predicates.
"""

import numpy as np

from robots.libero.v5_verification import moving_panel_points, vertical_face


VERSION = "microwave-public-RGBD-door-identity/1-dev"


def _rigid_fit(a, b):
    left, right = a.mean(axis=0), b.mean(axis=0)
    u, _, vt = np.linalg.svd((a - left).T @ (b - right))
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1] *= -1
        rotation = vt.T @ u.T
    return rotation, right - rotation @ left


def track_measured_door(previous_rgb, current_rgb, previous_world, current_world,
                        previous_mask, fixed_anchor, *, robot_mask=None):
    """Follow actual visual correspondences, then refit current depth points.

    The starting mask must belong to a previously measured door. A geometric
    front hint is not a valid starting mask. All returned points are sampled
    from current depth; the rigid fit/homography supplies identity guidance.
    The original plane consensus and extent thresholds remain in force.
    """
    import cv2

    evidence = {"version": VERSION, "source": "perception",
                "identity_basis": "previous_independent_door_mask_and_current_RGBD_correspondences",
                "private_labels_used": False, "stop_admitted": False}
    previous_mask = np.asarray(previous_mask, dtype=bool)
    previous_world, current_world = np.asarray(previous_world, dtype=float), np.asarray(current_world, dtype=float)
    shape = previous_mask.shape
    empty = np.zeros(shape, bool)
    if (np.shape(previous_rgb)[:2] != shape or np.shape(current_rgb)[:2] != shape
            or previous_world.shape != (*shape, 3) or current_world.shape != (*shape, 3)):
        return empty, None, {**evidence, "reason": "public_capture_shapes_differ"}
    old_gray = cv2.cvtColor(np.asarray(previous_rgb), cv2.COLOR_RGB2GRAY)
    new_gray = cv2.cvtColor(np.asarray(current_rgb), cv2.COLOR_RGB2GRAY)
    points = cv2.goodFeaturesToTrack(old_gray, maxCorners=600, qualityLevel=.001,
                                    minDistance=5, mask=previous_mask.astype(np.uint8) * 255,
                                    blockSize=5)
    evidence["seed_corners"] = 0 if points is None else len(points)
    if points is None or len(points) < 8:
        return empty, None, {**evidence, "reason": "independent_door_visual_support_missing"}
    params = dict(winSize=(31, 31), maxLevel=5,
                  criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, .01))
    forward, status, _ = cv2.calcOpticalFlowPyrLK(old_gray, new_gray, points, None, **params)
    backward, back_status, _ = cv2.calcOpticalFlowPyrLK(new_gray, old_gray, forward, None, **params)
    source, target = points[:, 0], forward[:, 0]
    keep = status[:, 0].astype(bool) & back_status[:, 0].astype(bool)
    keep &= np.linalg.norm(backward[:, 0] - source, axis=1) <= 1.5
    keep &= np.isfinite(target).all(axis=1)
    keep &= ((target >= 0) & (target < [shape[1] - 1, shape[0] - 1])).all(axis=1)
    source, target = source[keep], target[keep]
    evidence["mutual_visual_tracks"] = len(source)
    if len(source) < 8:
        return empty, None, {**evidence, "reason": "mutual_door_correspondences_missing"}
    old_pixels, new_pixels = np.rint(source).astype(int), np.rint(target).astype(int)
    a, b = previous_world[old_pixels[:, 1], old_pixels[:, 0]], current_world[new_pixels[:, 1], new_pixels[:, 0]]
    keep = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    keep &= (np.abs(a).sum(axis=1) > 1e-6) & (np.abs(b).sum(axis=1) > 1e-6)
    if robot_mask is not None:
        keep &= ~np.asarray(robot_mask, dtype=bool)[new_pixels[:, 1], new_pixels[:, 0]]
    a, b, source, target = a[keep], b[keep], source[keep], target[keep]
    evidence["current_public_depth_tracks"] = len(a)
    if len(a) < 8:
        return empty, None, {**evidence, "reason": "current_door_depth_support_missing"}
    # A tracked image corner on an occluder cannot supply rigid door identity.
    rng = np.random.default_rng(0)
    best = np.zeros(len(a), bool)
    for _ in range(128):
        selected = rng.choice(len(a), 3, replace=False)
        rotation, translation = _rigid_fit(a[selected], b[selected])
        residual = np.linalg.norm(a @ rotation.T + translation - b, axis=1)
        accepted = residual <= .008
        if accepted.sum() > best.sum():
            best = accepted
    evidence.update(rigid_tracks=int(best.sum()), rigid_fraction=float(best.mean()), rigid_distance_m=.008)
    if best.sum() < 8 or best.mean() < .55:
        return empty, None, {**evidence, "reason": "tracked_door_rigid_identity_not_supported"}
    homography, inliers = cv2.findHomography(source[best], target[best], cv2.RANSAC, 2.5)
    evidence["homography_tracks"] = 0 if inliers is None else int(inliers.sum())
    if homography is None or inliers.sum() < 8:
        return empty, None, {**evidence, "reason": "tracked_door_image_mapping_not_supported"}
    mapped = cv2.warpPerspective(previous_mask.astype(np.uint8), homography,
                                 (shape[1], shape[0]), flags=cv2.INTER_NEAREST).astype(bool)
    if robot_mask is not None:
        mapped &= ~np.asarray(robot_mask, dtype=bool)
    points_now = current_world[mapped]
    points_now = points_now[np.isfinite(points_now).all(axis=1) & (np.abs(points_now).sum(axis=1) > 1e-6)]
    cloud, consensus = moving_panel_points(points_now, fixed_anchor)
    face = vertical_face(cloud) if len(cloud) else None
    evidence.update(current_mask_pixels=int(mapped.sum()), panel_consensus=consensus)
    if face is None:
        return empty, None, {**evidence, "reason": "current_tracked_door_plane_not_measured"}
    # The dominant depth plane must contain the same tracked visual surface.
    normal = np.asarray(face["normal_xy"])
    supported = np.abs((b[best, :2] - face["centre"][:2]) @ normal) <= .008
    evidence["plane_support_fraction_of_rigid_tracks"] = float(supported.mean())
    if supported.mean() < .55:
        return empty, None, {**evidence, "reason": "depth_plane_does_not_match_tracked_identity"}
    from robots.libero.v5_microwave_capture import points_mask
    measured_mask = points_mask(current_world, cloud)
    return measured_mask, face, {**evidence, "reason": "current_depth_plane_with_tracked_door_identity"}
