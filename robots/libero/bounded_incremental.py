"""Incremental anchor refresh from public captures; no task-rule inputs."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation


def swept_bounds(geometry, controls, payload_reference=None, margin_m=.04):
    """Enclose measured 20 Hz hand/payload motion, including rotations.

    Boxes come from the static hand mesh and measured finger opening. The
    angular arc-length padding encloses rotation between successive samples;
    no planned waypoint or object simulator pose enters these bounds.
    """
    from itertools import product

    corners = np.asarray(list(product((0., 1.), repeat=3)))
    boxes = geometry['boxes']
    payload = None
    if payload_reference is not None and len(payload_reference.get('target', [])):
        robot = payload_reference['robot']
        payload = ((np.asarray(payload_reference['target'])-robot['eef_xyz_m'])
            @ Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix())
        lower, upper = payload.min(axis=0), payload.max(axis=0)
        payload = lower+corners*(upper-lower)
    lows, highs = [], []
    for control in controls:
        before, after = control['before'], control['after']
        rotations = [Rotation.from_quat(p['eef_quat_xyzw']) for p in (before, after)]
        angle = (rotations[1]*rotations[0].inv()).magnitude()
        for box in [*boxes, *([None] if payload is not None else [])]:
            ends, radius = [], 0.
            for robot, rotation in zip((before, after), rotations):
                if box is None:
                    local = payload
                else:
                    shift = np.asarray(box.get('slide_per_half_opening', [0., 0., 0.]))*robot['gripper_opening_m']/2
                    lower, upper = np.asarray(box['lower']), np.asarray(box['upper'])
                    local = lower+corners*(upper-lower)+shift
                radius = max(radius, float(np.linalg.norm(local, axis=1).max()))
                ends.append(local@rotation.as_matrix().T+robot['eef_xyz_m'])
            points = np.concatenate(ends)
            padding = margin_m+radius*angle
            lows.append(points.min(axis=0)-padding)
            highs.append(points.max(axis=0)+padding)
    return np.asarray(lows).reshape(-1, 3), np.asarray(highs).reshape(-1, 3)


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
    controls = getattr(adapter.p, '_bounded_perception_sweep', [])
    adapter.p._bounded_perception_sweep = []
    adapter._incremental_touched = set()
    adapter._incremental_route = []  # Discard legacy planned-route checkpoints.
    released = getattr(adapter, '_incremental_released_payload', False)
    adapter._incremental_released_payload = False
    if previous is None:
        adapter.incremental_evidence = [{'anchor_id':e.id,'changed':True,
            'reasons':['first_physical_capture'], 'capture_step':state.latest_step}
            for e in adapter.scene.entities.values() if e.name in requested]
        return requested
    pairs = ([{'before': previous, 'after': controls[0]['before']}]
        + [{'before': a['after'], 'after': b['before']} for a, b in zip(controls, controls[1:])]
        + [{'before': controls[-1]['after'], 'after': robot}]) if controls else [
            {'before': previous, 'after': robot}]
    untracked = any(c['before'] != c['after'] for c in pairs)
    if untracked or released:
        # Unobserved motion or a freely settling payload has no measured
        # rigid hand transform. Refresh rather than certify a stale cache.
        reason = 'untracked_robot_motion' if untracked else 'released_payload_settling'
        for entity in adapter.scene.entities.values():
            reasons[entity.id].add(reason)
    lows, highs = swept_bounds(adapter.geometry, controls, adapter.payload_reference)
    for entity in adapter.scene.entities.values():
        if ((highs >= entity.lower).all(axis=1)&(lows <= entity.upper).all(axis=1)).any():
            reasons[entity.id].add('hand_or_payload_swept_volume')
    supports = [row.split()[1:] for row in relations(list(adapter.scene.entities.values()),
        right_axis=adapter.scene.view_axes[0],front_axis=adapter.scene.view_axes[1])]
    for _ in adapter.scene.entities:
        changed = False
        for source, relation, target in supports:
            if (relation in {'on','in'} and target in getattr(adapter, '_incremental_support_changes', set())
                    and 'support_moved_or_contacted' not in reasons[source]):
                reasons[source].add('support_moved_or_contacted')
                changed = True
        if not changed:
            break
    records = [{'anchor_id':e.id,'capture_step':state.latest_step,
        'measurement_capture_step':e.source_step,'changed':bool(reasons[e.id]),
        'reasons':sorted(reasons[e.id]),'swept_margin_m':.04,
        'actual_control_samples':len(controls)}
        for e in adapter.scene.entities.values() if e.name in requested]
    adapter.incremental_evidence = records
    known = {e.name for e in adapter.scene.entities.values()}
    return sorted(set(requested)-known | {e.name for e in adapter.scene.entities.values() if reasons[e.id]})
