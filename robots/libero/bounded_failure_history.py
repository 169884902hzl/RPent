# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Unlock repeated failures only with measured physical scene motion."""
from __future__ import annotations

import numpy as np


def confirmed_changes(adapter, proposed, before_surfaces, confirmed_contacts=()):
    """Test suspected anchor motion with the existing public surface fit.

    A new ID, mask centre, camera pose or capture counter is not object
    motion. No physics steps means the simulated scene cannot have moved.
    When physics did run, fit along the measured displacement direction;
    its whole compatible interval must exceed the existing 1 cm gate.
    Missing/ambiguous surface evidence retains the failure history.
    """
    steps = adapter.p.env.execution_budget()['used_sim_steps']
    previous = getattr(adapter, '_failure_scene_sim_steps', steps)
    adapter._failure_scene_sim_steps = steps
    evidence = {'used_sim_steps': steps, 'previous_sim_steps': previous,
                'confirmed': [], 'anchors': [], 'private_truth_used': False}
    if not adapter.memory.counts or steps <= previous:
        evidence['reason'] = 'no_failure_history' if not adapter.memory.counts else 'no_physics_steps'
        return set(), evidence
    from robots.libero.bounded_payload import contact_axis_registration

    confirmed = set(confirmed_contacts)
    for key in sorted(proposed & set(adapter.previous_scene) - confirmed):
        entity = adapter.scene.entities[key]
        delta = np.asarray(entity.xyz)-adapter.previous_scene[key]
        distance = float(np.linalg.norm(delta))
        if distance <= .01:
            continue
        source = np.asarray(before_surfaces.get(key, [])).reshape(-1, 3)
        current = np.asarray(adapter.scene.measurement_clouds.get(key, [])).reshape(-1, 3)
        direction = delta/distance
        axis = np.eye(3)[np.argmin(np.abs(direction))]
        tangent = np.cross(direction, axis)
        tangent /= np.linalg.norm(tangent)
        frame = np.column_stack((direction, tangent, np.cross(direction, tangent)))
        fit = contact_axis_registration(source@frame, current@frame, 0, distance,
            query_workers=adapter.registration_query_workers)
        interval = fit.get('compatible_axis_interval_m')
        moved = bool(fit['accepted'] and interval is not None and interval[0] > .01)
        if moved:
            confirmed.add(key)
        evidence['anchors'].append({'anchor_id': key, 'centre_delta_m': delta.tolist(),
            'confirmed': moved, 'surface_fit': fit})
    evidence['confirmed'] = sorted(confirmed)
    evidence['reason'] = 'public_surface_motion_check'
    return confirmed, evidence
