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
        'compact_infeasible_candidates_v1', 'lazy_planning_v1', 'schema6_v1', 'public_progress',
        'memory', '_failed_move_anchors', '_move_approach_by_anchor', 'guarded_move_v1',
        '_stationary_observe_modes', '_progress_normals', 'rendered_self_filter_v1', '_vla_failed_options',
        'verify_instance_crops_v1','vla_options_v2','human_available')
    adapter = object.__new__(MeasuredSkillAdapter)
    adapter.__dict__.update({key: getattr(original, key) for key in names if hasattr(original, key)})
    scene_fields = ('entities', 'measurement_clouds', 'dual_view_fusion_v1', 'view_axes', '_scores')
    adapter.scene = SimpleNamespace(**{key: getattr(original.scene, key) for key in scene_fields})
    adapter.scene.rgbd_mask_tracking_v1 = getattr(original.scene,'rgbd_mask_tracking_v1',False)
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


def rebuild_schema6_captured_request(state, request, *, progress=None, progress_normals=None):
    """Rebuild the current catalog from a trusted captured public observation.

    This does not remeasure a scene or step physics. Historical snapshots may
    omit failure/progress history; those resets are explicit migration flags.
    Private goals are retained only in the returned annotation state.

    Returns:
        The rebuilt annotation state, public request, and ID/provenance flags.
    """
    from rpent.skill_package import VERSION as SCHEMA_VERSION
    from rpent.skill_package.contract import FailureMemory, identity
    from rpent.skill_package.progress import PublicProgress,DEFAULT_STAGNANT_DECISIONS

    if SCHEMA_VERSION not in {'bounded-skills/6','bounded-skills/7'}:
        raise ValueError('captured catalog reconstruction requires schema6 or schema7 source')
    if state['version'] != VERSION or state['request_sha256'] != request_digest(request):
        raise ValueError('captured state belongs to a different request or version')
    supported=(3,4,5,6,7) if SCHEMA_VERSION=='bounded-skills/7' else (3,4,5,6)
    if request['schema_version'] not in {f'bounded-skills/{v}' for v in supported}:
        raise ValueError('unsupported captured request version')
    if request.get('execution_prefix') is not None:
        raise ValueError('committed legacy prefix requires a new capture after it completes')
    if not isinstance(state['adapter'].p.env, FrozenSensors):
        raise ValueError('catalog reconstruction requires a frozen CPU annotation state')
    rebuilt = copy.deepcopy(state)
    adapter = rebuilt['adapter']
    receipt_migrations=[]
    for index,receipt in enumerate(adapter.receipts):
        if (receipt.get('schema_version') in {f'bounded-skills/{v}' for v in supported}
                and receipt['schema_version'] != SCHEMA_VERSION):
            before=copy.deepcopy(receipt)
            receipt['schema_version']=SCHEMA_VERSION
            validate(receipt)
            if {k:v for k,v in receipt.items() if k!='schema_version'} != {
                    k:v for k,v in before.items() if k!='schema_version'}:
                raise AssertionError('receipt migration changed a measurement')
            receipt_migrations.append({'index':index,'from':before['schema_version'],'to':SCHEMA_VERSION})
    had_history = 'memory' in vars(adapter)
    was_schema6 = adapter.schema6_v1
    had_progress = 'public_progress' in vars(adapter) and was_schema6
    adapter.schema6_v1 = adapter.lazy_planning_v1 = True
    adapter.request_consequence_workers = 1
    adapter.record_public_geometry = False
    for screen in adapter._cloud_and_ik.screens.values():
        if not hasattr(screen, '_endpoint_ik_cache'):
            screen._endpoint_ik_cache = {}
    if progress is not None:
        adapter.public_progress = copy.deepcopy(progress)
        adapter._progress_normals = copy.deepcopy(progress_normals or {})
    elif not had_progress:
        adapter.public_progress = PublicProgress(DEFAULT_STAGNANT_DECISIONS)
    if not had_history or not was_schema6:
        prior = adapter.memory if had_history else None
        adapter.memory = FailureMemory()
        adapter._failed_move_anchors = set()
        adapter._move_approach_by_anchor = {}
        # Only the published failure counts are known. Missing history must
        # not be invented from task progress, private goals or later outcomes.
        failures = ([(dict(skill=json.loads(key)[0], parameters=json.loads(key)[1]),
            count, prior.last.get(key), prior.cooldown.get(key, 0))
            for key, count in prior.counts.items()] if prior is not None else
            [(c, c['recent_failures'], c.get('last_failure'), 0) for c in request['candidates']])
        for candidate, count, reason, cooldown in failures:
            public = copy.deepcopy(candidate)
            if public['skill'] == 'move_to':
                public['parameters'] = {'anchor_id': public['parameters']['anchor_id']}
                if count:
                    adapter._failed_move_anchors.add(public['parameters']['anchor_id'])
            key = identity(public)
            adapter.memory.counts[key] = max(adapter.memory.counts.get(key, 0), count)
            adapter.memory.cooldown[key] = max(adapter.memory.cooldown.get(key, 0), cooldown)
            if reason:
                adapter.memory.last[key] = reason
    entities = [e for e in adapter.scene.entities.values() if adapter._has_anchor(e)]
    current = adapter._request_from_measured_plans(entities, k=request['max_actions'])
    rebuilt['request_sha256'] = request_digest(current)
    by_identity = {identity(c): c['id'] for c in current['candidates']}
    old_to_new, default_old = {}, {}
    for candidate in request['candidates']:
        public = copy.deepcopy(candidate)
        if public['skill'] == 'move_to':
            params = public['parameters']
            if params.get('approach') == 'above' and params.get('path') == 'over':
                default_old[params['anchor_id']] = public['id']
            public['parameters'] = {'anchor_id': params['anchor_id']}
        old_to_new[candidate['id']] = by_identity.get(identity(public))
    flags = {'source_request_sha256': state['request_sha256'],
        'request_sha256': rebuilt['request_sha256'], 'old_to_new': old_to_new,
        'old_to_new_candidate_ids': old_to_new,
        'priority_reference_old_move_by_anchor': default_old,
        'default_old_candidate_id_by_new_id': {c['id']: None for c in current['candidates']
            if c['skill'] == 'move_to'},
        'default_resolution': 'unresolved: requires complete route planning; above/over is priority only',
        'prefix_compatible': {}, 'unknown_reasons': ['effective_default_and_legacy_prefixes_not_resolved'],
        'requires_prefix_relabel': True,
        'committed_prefix_present': False, 'failure_history_incomplete': not had_history,
        'failure_history_projected_to_merged_catalog': not was_schema6,
        'progress_history_reset': not had_progress, 'contact_plans_reused': True,
        'receipt_protocol_migrations':receipt_migrations,
        'measurement_source': 'captured_public_rgbd_and_proprioception; no new sensor capture',
        'physics_steps': 0, 'gpu_used': False, 'training_authorized': False}
    return rebuilt, current, flags


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


def rebuild_saved_public_screens(adapter):
    """Apply current collision rules to saved raw public screen measurements.

    Legacy annotations have no RGB image or camera calibration. They use
    the current public mesh-hull self filter, rather than claiming a new
    rendered capture/SAM mask. No old collision/IK verdict is inherited.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation
    from robots.libero.bounded_obstacles import build_obstacles,subtract_instances
    from robots.libero.bounded_screen import PublicRouteScreen
    from robots.libero.bounded_self_filter import (
        ROBOT_FILTER_MARGIN_M,remove_current_gripper,remove_visual_robot)
    from robots.libero.v5_geometric_grasp import _voxel

    robot=measured_robot(adapter.p)
    originals=adapter._cloud_and_ik.screens
    held=originals.get(adapter.held) if adapter.held else None
    held_pixels=held.measured_target_points if held is not None else np.empty((0,3))
    captures={};screens={}
    for key,old in originals.items():
        if not isinstance(old,PublicRouteScreen):
            raise ValueError('saved screen does not contain measured route geometry')
        raw=old.measured_scene_points
        digest=hashlib.sha256(np.ascontiguousarray(raw).tobytes()).hexdigest()
        ik=old.ik.with_measured_robot(robot)
        ik.use_batched_kernel=False  # Keep deterministic source-owned warm solves.
        if digest not in captures:
            points,_=remove_current_gripper(raw,robot['eef_xyz_m'],robot['eef_quat_xyzw'],
                old.geometry,robot['gripper_opening_m'],surface_margin_m=ROBOT_FILTER_MARGIN_M)
            points,_=ik.remove_measured_arm(points,tolerance_m=ROBOT_FILTER_MARGIN_M)
            points,_=remove_visual_robot(points,ik,surface_margin_m=ROBOT_FILTER_MARGIN_M)
            captures[digest]=build_obstacles(points)
        structure=captures[digest]
        def present(points):
            points=np.asarray(points).reshape(-1,3)
            if not len(points):return points
            distance=structure['tree'].query(points,distance_upper_bound=np.nextafter(1e-6,np.inf))[0]
            return points[distance<=1e-6]
        target=present(old.measured_target_points)
        carried=present(held_pixels)
        points=subtract_instances(structure,target,carried,held_margin_m=ROBOT_FILTER_MARGIN_M)
        payload=(_voxel(carried,.002)-robot['eef_xyz_m'])@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
        screens[key]=PublicRouteScreen(points,old.geometry,ik,opening=old.opening,
            contact_points=np.empty((0,3)) if key==adapter.held else _voxel(target,.002),
            contact_allowed=old.contact_allowed,payload_local=payload,
            initial_pose={'xyz_m':robot['eef_xyz_m'],'quat_xyzw':robot['eef_quat_xyzw']},
            measured_scene_points=structure['points'],measured_target_points=target,
            capture_points=structure['points'],capture_key=structure['key'])
        screens[key].contact_axis=getattr(old,'contact_axis',None)
        screens[key].contact_origin=getattr(old,'contact_origin',None)
    adapter._cloud_and_ik=FrozenScreens(screens)
    if not hasattr(adapter,'withdrawal_contact'):
        adapter.withdrawal_contact=None
    adapter._screen_cache={}
    adapter._instance_cache={key:screen.measured_target_points for key,screen in screens.items() if key is not None}
    adapter._base_geometry=(screens[None].measured_scene_points,screens[None].ik)
    adapter._capture_obstacles=None
    adapter._self_filtered_capture=None
    adapter.instance_boundary_evidence={}
    adapter.public_geometry_evidence={}
    return {'scope':'saved_raw_rgbd_public_robot_and_current_12mm_static_mesh_filter',
        'collision_verdicts_reused':False,'new_camera_capture':False,'rpc_calls':0,
        'screens':len(screens),'shared_captures':len(captures)}
