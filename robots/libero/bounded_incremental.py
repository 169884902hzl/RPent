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
    if not hasattr(state, 'load_bytes'):
        return requested
    frames = {camera: (np.asarray(state.load(camera+'_high.png')),
        np.asarray(state.load(camera+'_world_high.npz'))) for camera in ('agentview', 'wrist')}
    previous = getattr(adapter, '_incremental_previous', None)
    adapter._incremental_previous = frames
    if previous is None:
        return requested
    dirty = set(getattr(adapter, '_incremental_touched', set()))
    dirty.update(key for key in (adapter.held, adapter.active) if key)
    routes = getattr(adapter, '_incremental_route', [])
    records = []
    for entity in adapter.scene.entities.values():
        if entity.name not in requested:
            continue
        views = {camera: roi_change(previous[camera][0], frames[camera][0],
            previous[camera][1], frames[camera][1], entity.lower, entity.upper)
            for camera in frames}
        evidence = {'changed': any(e['changed'] for e in views.values()), 'views': views}
        if routes:
            points = np.asarray(routes)
            near = ((points >= np.asarray(entity.lower)-.10)
                & (points <= np.asarray(entity.upper)+.10)).all(axis=1).any()
            if near:
                dirty.add(entity.id)
        records.append({'anchor_id': entity.id, 'capture_step': state.latest_step,
            'measurement_capture_step': entity.source_step, **evidence})
        if evidence['changed']:
            dirty.add(entity.id)
    adapter.incremental_evidence = records
    adapter._incremental_touched = set()
    adapter._incremental_route = []
    known = {e.name for e in adapter.scene.entities.values()}
    return sorted(set(requested)-known | {e.name for e in adapter.scene.entities.values() if e.id in dirty})
