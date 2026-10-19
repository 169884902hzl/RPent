# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Spawn CPU consequence workers from detached public measurements."""
from __future__ import annotations

import copy
import multiprocessing
import os
from types import SimpleNamespace

from robots.libero.bounded_motion import measured_robot
from robots.libero.bounded_screen import PublicRouteScreen

_prediction = None
_request_adapter = None


class CapturedSensors:
    """Captured robot/budget data with no environment or stepping interface."""

    def __init__(self, robot, budget):
        self.robot, self.budget = robot, budget

    def raw_obs(self):
        return {'robot0_eef_pos': self.robot['eef_xyz_m'],
                'robot0_eef_quat': self.robot['eef_quat_xyzw'],
                'robot0_gripper_qpos': self.robot['finger_positions_m'],
                'robot0_joint_pos': self.robot['joint_positions_rad']}

    def execution_budget(self):
        return dict(self.budget)


class CapturedDepth:
    """Retain exact captured depth pixels needed for support alignment."""

    def __init__(self, state):
        self.latest_step = state.latest_step
        self.images = {camera+'_world_high.npz': state.load(camera+'_world_high.npz')
                       for camera in ('agentview', 'wrist')}

    def load(self, name):
        return self.images[name]


class CapturedScreens:
    """Exact current route graphs, without callbacks into the live adapter."""

    def __init__(self, screens):
        self.screens = screens

    def __call__(self, anchor_id=None, *, contact=False):
        return self.screens[anchor_id, contact]


def _detach_adapter(original, robot, budget):
    clone = object.__new__(type(original))
    names = ('xml', 'robot_xml', 'geometry', 'config', 'allow_vla', 'history',
             'held', 'active', 'grasp_reference', 'payload_reference', 'target_cache',
             'plans', 'committed_grasps', 'receipts', 'revision', '_proprio_sample',
             'precontact_instance_surface_v1', 'legacy_chunk_boundaries_v1',
             'compact_infeasible_candidates_v1')
    clone.__dict__.update({name: getattr(original, name) for name in names})
    scene_fields = ('entities', 'measurement_clouds', 'dual_view_fusion_v1', 'view_axes', '_scores')
    clone.scene = SimpleNamespace(**{name: getattr(original.scene, name) for name in scene_fields})
    if hasattr(original.scene, 'work_surface_measurement'):
        clone.scene.work_surface_measurement = original.scene.work_surface_measurement
    clone.p = SimpleNamespace(env=CapturedSensors(robot, budget))
    for name in ('_bounded_motion_samples', '_bounded_control_index', '_bounded_rest_reference'):
        if hasattr(original.p, name):
            setattr(clone.p, name, getattr(original.p, name))
    clone.ex = SimpleNamespace(instruction=original.ex.instruction,
        toolkit=SimpleNamespace(_state=CapturedDepth(original.ex.toolkit._state)))
    clone.record_public_geometry = False
    clone.candidate_diagnostics = []
    clone._screen_cache = {}
    return clone


def detach_prediction(prediction):
    """Remove clients, renderer and unused collision graphs before spawning.

    The returned graph contains only public request/measurement data, static
    robot geometry and conditional state. No private oracle label is copied.
    """
    if not isinstance(prediction.base_screen, PublicRouteScreen):
        raise ValueError('CPU consequence workers require a public measured route screen')
    result = copy.copy(prediction)
    result.original_clouds = dict(prediction.original_clouds)
    for anchor in prediction.request['anchors']:
        result.original_clouds[anchor['id']] = prediction._original_target(anchor['id'])
    # _screen already owns the exact world/payload and original target
    # pixels; per-anchor source collision graphs are no longer inputs.
    result.source_adapter = None
    result.adapter = clone = _detach_adapter(prediction.adapter, result.sensor, result.budget)
    clone._cloud_and_ik = result._screen
    return result


def _initialize(prediction):
    global _prediction
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    _prediction = prediction


def _candidate(original):
    _prediction.adapter.candidate_diagnostics = []
    candidate = _prediction.candidate(original)
    return candidate, _prediction.adapter.candidate_diagnostics


def predict_candidates(prediction, originals, workers):
    """Return ordered consequences using owned CPU processes, without fork."""
    if not originals:
        return []
    captured = detach_prediction(prediction)
    with multiprocessing.get_context('spawn').Pool(
            workers, initializer=_initialize, initargs=(captured,)) as pool:
        rows = pool.map(_candidate, originals, chunksize=4)
    for _, diagnostics in rows:
        prediction.adapter.candidate_diagnostics.extend(diagnostics)
    return [candidate for candidate, _ in rows]


def capture_request_adapter(adapter, options):
    """Freeze current public screens after contact plans have been generated."""
    from robots.libero.bounded_skills import MOTION_SKILLS

    clone = _detach_adapter(adapter, measured_robot(adapter.p), adapter.p.env.execution_budget())
    screens = {}
    for skill, parameters in options:
        if skill not in MOTION_SKILLS:
            continue
        key = parameters.get('anchor_id', parameters.get('target_id'))
        if key is None and skill in {'nudge', 'rotate_wrist'}:
            key = adapter.active
        contact = skill in {'descend', 'lower', 'nudge'} or (
            skill in {'lift', 'rotate_wrist'} and adapter.active is not None)
        if (key, contact) not in screens:
            screens[key, contact] = adapter._cloud_and_ik(key, contact=contact)
    clone._cloud_and_ik = CapturedScreens(screens)
    return clone


def _initialize_request(adapter):
    global _request_adapter
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    _request_adapter = adapter


def _request_candidate(option):
    skill, parameters = option
    _request_adapter.candidate_diagnostics = []
    candidate = _request_adapter._candidate(skill, parameters)
    return candidate, _request_adapter.candidate_diagnostics


def request_candidates(adapter, options, workers):
    """Evaluate current-state options in source order using CPU-only spawn."""
    if not options:
        return []
    captured = capture_request_adapter(adapter, options)
    with multiprocessing.get_context('spawn').Pool(
            workers, initializer=_initialize_request, initargs=(captured,)) as pool:
        rows = pool.map(_request_candidate, options, chunksize=4)
    for _, diagnostics in rows:
        adapter.candidate_diagnostics.extend(diagnostics)
    return [candidate for candidate, _ in rows if candidate is not None]
