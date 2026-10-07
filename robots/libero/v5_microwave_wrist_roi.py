# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Refit current wrist depth inside an independently measured public fixed ROI."""

import math

import numpy as np

from robots.libero.v5_microwave_door_temporal import MicrowaveDoorTemporalConfig, _plane
from robots.libero.v5_verification import vertical_face


VERSION = 'microwave-current-public-wrist-fixed-roi/1-dev'


def fit_wrist_fixed_roi(world, reference, reference_cloud, *, source_step):
    """Use agentview only to bind the ROI; fit exclusively actual wrist pixels."""
    world, reference_cloud = np.asarray(world), np.asarray(reference_cloud)
    mask = np.zeros(world.shape[:2], dtype=bool)
    empty = np.empty((0, 3), dtype=float)
    evidence = {'version': VERSION, 'source': 'perception', 'status': 'unmeasured',
        'source_step': source_step, 'roi_source_cameras': ['agentview'],
        'fit_source_cameras': ['wrist'], 'reference_step': reference.get('source_step'),
        'fit_uses_reference_points': False, 'wrist_points': 0,
        'reference_identity': {key: reference.get(key) for key in ('path', 'sha256', 'mask_id')}}
    config = MicrowaveDoorTemporalConfig()
    if (reference.get('source') != 'perception' or reference.get('source_cameras') != ['agentview']
            or reference.get('source_step') != source_step or reference.get('mask_count') != 1
            or reference.get('frame_id') != 'world' or reference.get('length_unit') != 'm'
            or world.ndim != 3 or world.shape[-1] != 3
            or reference_cloud.ndim != 2 or reference_cloud.shape[1:] != (3,)
            or len(reference_cloud) < 30 or not np.isfinite(reference_cloud).all()):
        return None, evidence | {'reason': 'current_independent_agentview_reference_missing'}, empty, mask
    face, reason = _plane(reference, {'source_step': source_step}, config)
    if reason:
        return None, evidence | {'reason': 'reference_' + reason}, empty, mask
    lo, hi = np.quantile(reference_cloud, (.02, .98), axis=0)
    normal = np.asarray(face['normal_xy'])
    # The existing fixed-front patch selector uses observed bounds +2mm and
    # an8mm plane slab. Neither selection introduces simulator geometry.
    mask = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    mask &= ((world >= lo - .002) & (world <= hi + .002)).all(axis=-1)
    mask &= np.abs((world[..., :2] - face['centre'][:2]) @ normal) <= .008
    points = world[mask]
    evidence.update(roi_lower_world_m=lo.tolist(), roi_upper_world_m=hi.tolist(),
                    roi_margin_m=.002, maximum_plane_selection_distance_m=.008, wrist_points=len(points))
    fit = vertical_face(points)
    if fit is None:
        return None, evidence | {'reason': 'current_wrist_fixed_patch_not_measured'}, points, mask
    delta_angle = math.degrees(math.acos(float(np.clip(abs(normal @ fit['normal_xy']), 0., 1.))))
    delta_normal = abs(float((np.asarray(fit['centre'][:2]) - face['centre'][:2]) @ normal))
    evidence.update(measured_plane=fit, reference_angle_difference_deg=delta_angle,
                    reference_normal_drift_m=delta_normal)
    if (fit['residual_p90_m'] > config.maximum_plane_residual_m
            or delta_angle > config.maximum_reference_angle_deg
            or delta_normal > config.maximum_reference_drift_m):
        return None, evidence | {'reason': 'current_wrist_reference_disagrees'}, points, mask
    return fit, evidence | {'status': 'measured', 'reason': 'current_wrist_depth_supported_fixed_roi'}, points, mask
