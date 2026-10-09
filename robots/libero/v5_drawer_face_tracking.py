"""Track measured drawer-face texture across public RGB-D captures."""

from __future__ import annotations

import numpy as np

VERSION = "public-drawer-face-flow/1-dev"


def track_face(before_rgb, before_world, after_rgb, after_world, measurement):
    """Estimate axial displacement; return unknown if correspondence is weak.

    Inputs are camera images, measured world point maps, and an initial public
    face/band. No simulator state or task predicate participates in tracking.
    """
    import cv2

    evidence = {"version": VERSION, "source": "calibrated_rgbd_texture_correspondence",
                "private_values_used": False, "status": "unmeasured"}
    face = measurement.get("moving")
    bounds = measurement.get("current_part_bounds")
    axis = measurement.get("outward_axis_xy")
    if face is None or bounds is None or axis is None:
        return {**evidence, "reason": "initial_measured_face_or_band_missing"}
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    tangent = np.array([-axis[1], axis[0]])
    centre = np.asarray(face["centre"], dtype=float)
    lower, upper = np.asarray(bounds["lower"]), np.asarray(bounds["upper"])
    first = np.asarray(before_world, dtype=float)
    last = np.asarray(after_world, dtype=float)
    if (first.shape != (*before_rgb.shape[:2], 3)
            or last.shape != (*after_rgb.shape[:2], 3)
            or before_rgb.shape != after_rgb.shape):
        return {**evidence, "reason": "rgbd_shape_mismatch"}
    mask = (np.isfinite(first).all(axis=2)
            & (np.abs((first[:, :, :2] - centre[:2]) @ axis) < .01)
            & (first[:, :, 2] >= lower[2]) & (first[:, :, 2] <= upper[2])
            & (first[:, :, 0] >= lower[0]) & (first[:, :, 0] <= upper[0]))
    gray0 = cv2.cvtColor(before_rgb, cv2.COLOR_RGB2GRAY)
    gray1 = cv2.cvtColor(after_rgb, cv2.COLOR_RGB2GRAY)
    seeds = cv2.goodFeaturesToTrack(gray0, 100, .005, 5, mask=mask.astype(np.uint8) * 255)
    if seeds is None:
        return {**evidence, "reason": "initial_face_texture_unmeasured", "mask_pixels": int(mask.sum())}
    positions, status, _ = cv2.calcOpticalFlowPyrLK(gray0, gray1, seeds, None,
                                                   winSize=(21, 21), maxLevel=4)
    reverse, reverse_status, _ = cv2.calcOpticalFlowPyrLK(gray1, gray0, positions, None,
                                                        winSize=(21, 21), maxLevel=4)
    error = np.linalg.norm(reverse[:, 0] - seeds[:, 0], axis=1)
    start = np.rint(seeds[:, 0]).astype(int)
    end = np.rint(positions[:, 0]).astype(int)
    keep = ((status[:, 0] == 1) & (reverse_status[:, 0] == 1) & (error < 1.)
            & (end[:, 0] >= 0) & (end[:, 0] < gray1.shape[1])
            & (end[:, 1] >= 0) & (end[:, 1] < gray1.shape[0]))
    start, end = start[keep], end[keep]
    delta = last[end[:, 1], end[:, 0]] - first[start[:, 1], start[:, 0]]
    valid = (np.isfinite(delta).all(axis=1) & (np.abs(delta[:, 2]) < .025)
             & (np.abs(delta[:, :2] @ tangent) < .025)
             & (np.abs(delta[:, :2] @ axis) <= .35))
    axial = delta[valid, :2] @ axis
    evidence.update(mask_pixels=int(mask.sum()), texture_seeds=len(seeds),
                    forward_backward_matches=len(delta), axis_consistent_matches=len(axial))
    if len(axial) < 6:
        return {**evidence, "reason": "insufficient_rigid_axial_correspondences"}
    displacement = float(np.median(axial))
    residual = float(np.quantile(np.abs(axial - displacement), .9))
    evidence.update(axial_displacement_m=displacement, axial_residual_p90_m=residual,
                    tracked_face_centre_m=(centre + np.r_[axis * displacement, 0.]).tolist())
    if residual > .01:
        return {**evidence, "reason": "nonrigid_or_mismatched_texture_tracks"}
    return {**evidence, "status": "measured", "reason": "rigid_face_correspondence"}
