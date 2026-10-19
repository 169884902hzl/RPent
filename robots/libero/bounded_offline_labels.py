# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Private CPU labels for arbitrary prefixes, without an environment or RPC.

Only load trusted local snapshots. These snapshots include private goal labels
and must never be passed to a model or merged into a public request.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import multiprocessing
import pickle
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from robots.libero.bounded_chunk import PublicPrefixPrediction
from robots.libero.bounded_motion import measured_robot
from robots.libero.bounded_oracle import JUDGE_VERSION, BoundedOracle, NoPublicOption
from robots.libero.bounded_skills import MeasuredSkillAdapter
from rpent.skill_package.contract import (
    LEGALITY_VERSION,
    is_boundary,
    legal_after,
    validate,
)

VERSION = 'libero-offline-prefix-label/1'
_worker_prediction = None


def _initialize_prediction_worker(prediction):
    global _worker_prediction
    _worker_prediction = prediction


def _predict_candidate(candidate):
    return _worker_prediction.candidate(candidate)


class OfflinePrefixPrediction(PublicPrefixPrediction):
    """Parallelize only trusted, frozen CPU annotation snapshots."""

    def __init__(self, adapter, request, workers):
        super().__init__(adapter, request)
        self.workers = workers

    def _candidates(self, originals):
        if self.workers == 1 or not originals:
            return super()._candidates(originals)
        # Fork inherits the measured predictor without pickling its bound
        # sensor methods. Each process owns its IK/cloud caches, and ordered
        # map preserves the public candidate order. No live adapter is used.
        with multiprocessing.get_context('fork').Pool(
                self.workers, initializer=_initialize_prediction_worker, initargs=(self,)) as pool:
            return pool.map(_predict_candidate, originals, chunksize=4)


def request_digest(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class FrozenSensors:
    """Expose captured proprioception and budget, with no stepping method."""

    def __init__(self, robot, budget):
        self.robot, self.budget = robot, budget

    def raw_obs(self):
        return {'robot0_eef_pos': self.robot['eef_xyz_m'],
                'robot0_eef_quat': self.robot['eef_quat_xyzw'],
                'robot0_gripper_qpos': self.robot['finger_positions_m'],
                'robot0_joint_pos': self.robot['joint_positions_rad']}

    def execution_budget(self):
        return dict(self.budget)


class FrozenScreens:
    """Retain the exact captured screen graph, including numerical IK caches."""

    def __init__(self, screens):
        self.screens = screens

    def __call__(self, anchor_id=None, *, contact=False):
        return self.screens[anchor_id]


class FrozenDepth:
    """Keep captured world images available for measured support fitting."""

    def __init__(self, state):
        self.latest_step = state.latest_step
        self.images = {camera+'_world_high.npz': state.load(camera+'_world_high.npz')
                       for camera in ('agentview', 'wrist')}

    def load(self, name):
        return self.images[name]


def capture_annotation_state(oracle, request, *, status=None):
    """Freeze the current measured adapter and private rules before selection.

    Cloud preparation is CPU work and may read saved depth pixels. No camera
    capture, physics step, or private object coordinate is requested here.
    """
    validate(request)
    original = oracle.adapter
    # Explicit fields avoid serializing an executor, client, renderer or lock.
    names = ('xml', 'robot_xml', 'geometry', 'config', 'allow_vla', 'history',
        'held', 'active', 'grasp_reference', 'payload_reference', 'target_cache',
        'plans', 'committed_grasps', 'receipts', 'revision', '_proprio_sample',
        'precontact_instance_surface_v1', 'legacy_chunk_boundaries_v1',
        'compact_infeasible_candidates_v1')
    adapter = object.__new__(MeasuredSkillAdapter)
    adapter.__dict__.update({key: getattr(original, key) for key in names})
    scene_fields = ('entities', 'measurement_clouds', 'dual_view_fusion_v1', 'view_axes', '_scores')
    adapter.scene = SimpleNamespace(**{key: getattr(original.scene, key) for key in scene_fields})
    if hasattr(original.scene, 'work_surface_measurement'):
        adapter.scene.work_surface_measurement = original.scene.work_surface_measurement
    robot = measured_robot(original.p)
    adapter.p = SimpleNamespace(env=FrozenSensors(robot, original.p.env.execution_budget()))
    for name in ('_bounded_motion_samples', '_bounded_control_index', '_bounded_rest_reference'):
        if hasattr(original.p, name):
            setattr(adapter.p, name, getattr(original.p, name))
    adapter.ex = SimpleNamespace(instruction=original.ex.instruction,
        toolkit=SimpleNamespace(_state=FrozenDepth(original.ex.toolkit._state)))
    adapter.candidate_diagnostics = []
    adapter.record_public_geometry = False
    screens = {None: original._cloud_and_ik()}
    screens.update({anchor['id']: original._cloud_and_ik(anchor['id'], contact=True)
                    for anchor in request['anchors']})
    adapter._cloud_and_ik = FrozenScreens(screens)
    state = {'version': VERSION, 'request_sha256': request_digest(request),
        'adapter': adapter, 'private_status': status if status is not None else oracle.rpc.call('oracle.status'),
        'binding': {key: value for key, value in oracle.binding.__dict__.items() if key != 'rpc'}}
    # Detach shared buffers and warm starts once, retaining internal aliasing.
    return copy.deepcopy(state)


def annotate_prefix(state, request, prefix, *, workers=1):
    """Return public legal and private rule-acceptable IDs after any prefix.

    Acceptable is conditional on the prefix's receipt assumptions. It is not
    measured branch success. Invalid public prefixes are rejected; an empty
    acceptable set is explicit and is never replaced with the oracle's path.
    """
    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError('workers must be a positive integer')
    if workers > 1:
        if not isinstance(state['adapter'].p.env, FrozenSensors):
            raise ValueError('parallel annotation requires a frozen CPU snapshot')
        if threading.current_thread() is not threading.main_thread():
            raise ValueError('parallel annotation must run from the CPU process main thread')
        torch = sys.modules.get('torch')
        if torch is not None and torch.cuda.is_initialized():
            raise ValueError('parallel annotation cannot fork an initialized CUDA process')
    validate(request)
    if state['version'] != VERSION or state['request_sha256'] != request_digest(request):
        raise ValueError('offline annotation state belongs to a different request or version')
    prefix = list(prefix)
    legal = list(legal_after(request, prefix))
    result = {'version': VERSION, 'legality_version': LEGALITY_VERSION,
        'request_sha256': state['request_sha256'], 'observation_id': request['observation_id'],
        'revision': request['revision'], 'prefix': prefix, 'legal': legal,
        'rule_acceptable': [], 'selected': None, 'measured_success': [], 'measured_failure': [],
        'judge': JUDGE_VERSION, 'model_visible': False,
        'physics_steps': 0, 'gpu_used': False, 'conditional_on_receipt_checks': [],
        'requires_measurement': False, 'status': 'terminal_prefix' if not legal else 'labeled'}
    if not legal:
        return result
    adapter = copy.deepcopy(state['adapter'])
    oracle = BoundedOracle(None, adapter)
    oracle.binding.__dict__.update(copy.deepcopy(state['binding']))
    prediction = OfflinePrefixPrediction(adapter, request, workers)
    oracle.adapter = prediction.adapter
    for cid in prefix:
        context = prediction.context()
        candidate = next((c for c in context['candidates'] if c['id'] == cid), None)
        if candidate is not None and is_boundary(candidate):
            raise ValueError('cannot predict beyond a control-handoff boundary')
        if candidate is None or candidate['consequences']['collision'] is True or candidate['consequences']['ik_reachable'] is False:
            return {**result, 'status': 'prefix_infeasible_in_predicted_state',
                'failed_prefix_id': cid, 'conditional_on_receipt_checks': prediction.assumptions}
        prediction.advance(candidate)
    context = prediction.context()
    current = {**request, 'candidates': [c for c in context['candidates'] if c['id'] in legal],
               'robot': context['predicted_robot']}
    try:
        chosen = oracle._choose_one(current, state['private_status'],
            predicted_prefix=bool(prefix) or request.get('execution_prefix') is not None)
    except NoPublicOption:
        return {**result, 'status': 'no_acceptable_public_option',
            'conditional_on_receipt_checks': context['assumptions']}
    acceptable = oracle._acceptable(current, state['private_status'],
        predicted_prefix=bool(prefix) or request.get('execution_prefix') is not None)
    acceptable.add(chosen['id'])
    if chosen['id'] not in legal or not acceptable <= set(legal):
        raise ValueError('offline oracle returned an option outside public legal_after')
    return {**result, 'rule_acceptable': [cid for cid in legal if cid in acceptable],
        'selected': chosen['id'], 'conditional_on_receipt_checks': context['assumptions'],
        'requires_measurement': any(row.get('await_prefix_measurement') for row in oracle.private_trace),
        'predicted_robot': context['predicted_robot']}


def save_annotation_state(path, state):
    """Write a private trusted snapshot, returning its integrity reference."""
    path = Path(path)
    raw = gzip.compress(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL), compresslevel=1, mtime=0)
    with path.open('xb') as stream:
        stream.write(raw)
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
        'version': VERSION, 'request_sha256': state['request_sha256'], 'model_visible': False}


def load_annotation_state(path, sha256):
    """Load only a hash-pinned, trusted private annotation snapshot."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError('offline annotation snapshot hash mismatch')
    return pickle.loads(gzip.decompress(raw))
