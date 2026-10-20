"""Incremental anchor refresh from public captures; no task-rule inputs."""
from __future__ import annotations

import numpy as np


def roi_change(previous_rgb, current_rgb, previous_world, current_world, lower, upper):
    """Compare fixed-camera pixels around the last measured anchor bounds."""
    a, b = np.asarray(previous_rgb), np.asarray(current_rgb)
    wa, wb = np.asarray(previous_world), np.asarray(current_world)
    if a.shape != b.shape or wa.shape != wb.shape:
        return {'changed': True, 'reason': 'capture_shape_changed'}
    lo, hi = np.asarray(lower)-.02, np.asarray(upper)+.02
    roi = (((wa >= lo) & (wa <= hi)).all(axis=-1)
        | ((wb >= lo) & (wb <= hi)).all(axis=-1))
    if roi.sum() < 8:
        return {'changed': True, 'reason': 'roi_unmeasured', 'pixels': int(roi.sum())}
    rgb_delta = np.max(np.abs(a[roi].astype(float)-b[roi]), axis=-1)
    depth_delta = np.linalg.norm(wa[roi]-wb[roi], axis=-1)
    changed_fraction = float(np.mean((rgb_delta > 3) | ~np.isfinite(depth_delta) | (depth_delta > .001)))
    return {'changed': changed_fraction > 0., 'reason': 'public_camera_roi_difference',
        'pixels': int(roi.sum()), 'changed_fraction': changed_fraction,
        'rgb_threshold': 3, 'depth_threshold_m': .001, 'fraction_threshold': 0.}


def refresh_names(adapter, requested):
    state = adapter.ex.toolkit._state
    from collections import defaultdict
    from robots.libero.bounded_motion import measured_robot
    from robots.libero.v5_state import relations

    reasons = defaultdict(set)
    for key in getattr(adapter, '_incremental_touched', set()):
        reasons[key].add('contacted_in_previous_chunk')
    if adapter.held:
        reasons[adapter.held].add('held_object')
    robot = measured_robot(adapter.p)
    previous = getattr(adapter, '_incremental_previous_robot', None)
    adapter._incremental_previous_robot = robot
    if previous is None:
        adapter.incremental_evidence = [{'anchor_id':e.id,'changed':True,
            'reasons':['first_physical_capture'], 'capture_step':state.latest_step}
            for e in adapter.scene.entities.values() if e.name in requested]
        return requested
    routes = getattr(adapter, '_incremental_route', [])
    points = np.asarray([previous['eef_xyz_m'], *routes, robot['eef_xyz_m']])
    # A sphere enclosing the static hand at any orientation, plus the
    # measured held extent. Segment AABBs conservatively enclose every
    # swept pose, including the connecting motion between 20 Hz samples.
    radius = max((np.linalg.norm(np.maximum(np.abs(b['lower']),np.abs(b['upper'])))
        for b in adapter.geometry['boxes']), default=.1)+.04
    payload = (adapter.payload_reference or {}).get('target')
    if payload is not None and len(payload):
        capture_robot = adapter.payload_reference['robot']
        radius = max(radius,float(np.linalg.norm(np.asarray(payload)-capture_robot['eef_xyz_m'],axis=1).max()))
    lows = np.minimum(points[:-1],points[1:])-radius
    highs = np.maximum(points[:-1],points[1:])+radius
    if not np.any(np.linalg.norm(points[1:]-points[:-1],axis=1) > 1e-6):
        lows, highs = np.empty((0,3)), np.empty((0,3))
    for entity in adapter.scene.entities.values():
        if ((highs >= entity.lower).all(axis=1)&(lows <= entity.upper).all(axis=1)).any():
            reasons[entity.id].add('hand_or_payload_swept_volume')
    supports = [row.split()[1:] for row in relations(list(adapter.scene.entities.values()),
        right_axis=adapter.scene.view_axes[0],front_axis=adapter.scene.view_axes[1])]
    for _ in adapter.scene.entities:
        changed = False
        for source, relation, target in supports:
            if (relation in {'on','in'} and target in set(getattr(adapter, '_last_scene_changes', set()))
                    and 'support_moved_or_contacted' not in reasons[source]):
                reasons[source].add('support_moved_or_contacted')
                changed = True
        if not changed:
            break
    records = [{'anchor_id':e.id,'capture_step':state.latest_step,
        'measurement_capture_step':e.source_step,'changed':bool(reasons[e.id]),
        'reasons':sorted(reasons[e.id]),'swept_radius_m':radius}
        for e in adapter.scene.entities.values() if e.name in requested]
    adapter.incremental_evidence = records
    adapter._incremental_touched = set()
    adapter._incremental_route = []
    known = {e.name for e in adapter.scene.entities.values()}
    return sorted(set(requested)-known | {e.name for e in adapter.scene.entities.values() if reasons[e.id]})
