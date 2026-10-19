# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measured LIBERO adapter for the shared bounded-skills contract.

No BDDL, oracle RPC or simulator object poses are read here. Candidate geometry
comes from dual-view RGB-D and public robot sensors. Category-specific logic
is confined to the existing grasp-region perception code.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_motion import (
    MotionConfig,
    SmoothMotion,
    measured_robot,
    settle_osc_hold,
    public_control,
)
from robots.libero.bounded_screen import PublicRouteScreen
from robots.libero.bounded_chunk import PublicPrefixPrediction, check_receipt, expected_receipt
from robots.libero.bounded_self_filter import (
    gripper_at_measured_fingers,
    gripper_visual_boxes,
    remove_current_gripper,
    remove_visual_robot,
)
from robots.libero.v5_geometric_grasp import panda_geometry, side_site_rotation
from robots.libero.v5_grasp_geometry import (
    clean_object_mask,
    complete_contact_surface,
    complete_crossview_boundary,
    complete_cylindrical_contact_surface,
    complete_instance_boundary,
    complete_planar_boundary,
    complete_sparse_instance_boundary,
    depth_components,
    measured_handle_axis,
    retain_crossview_semantic_fragments,
)
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import separate_target_points
from robots.libero.v5_state import fixture_actions
from robots.libero.v5_subtasks import measured_instance_description, subtask_phrase
from rpent.skill_package import VERSION
from rpent.skill_package.contract import (
    FailureMemory,
    compact_candidate,
    identity,
    is_boundary,
    selected,
    validate,
)
from rpent.skill_package.vla import DevelopmentHistory, VLABudget, run_fallback

MOTION_SKILLS = {"move_to", "align", "descend", "lift", "carry_to", "lower", "rotate_wrist", "nudge"}


class MeasuredSkillAdapter:
    """Enumerate public options and execute only exact selected IDs."""

    def __init__(self, executor, gripper_xml: str | Path, *, allow_vla: bool = True,
                 history: DevelopmentHistory | None = None, motion_config: MotionConfig = MotionConfig(),
                 record_public_geometry: bool = False, precontact_instance_surface_v1: bool = False,
                 legacy_chunk_boundaries_v1: bool = False,
                 compact_infeasible_candidates_v1: bool = True,
                 prefix_consequence_workers: int = 1,
                 request_consequence_workers: int = 1,
                 vla_budget: VLABudget = VLABudget()):
        if type(prefix_consequence_workers) is not int or prefix_consequence_workers < 1:
            raise ValueError('prefix_consequence_workers must be a positive integer')
        if type(request_consequence_workers) is not int or request_consequence_workers < 1:
            raise ValueError('request_consequence_workers must be a positive integer')
        self.ex, self.p, self.scene = executor, executor.p, executor.scene
        self.xml = Path(gripper_xml)
        self.geometry = panda_geometry(self.xml)
        if self.xml.is_file():
            self.geometry = {**self.geometry, 'visual_boxes': gripper_visual_boxes(str(self.xml))}
        self.robot_xml = self.xml.parent.parent/"robots/panda/robot.xml"
        self.allow_vla, self.history = allow_vla, history or DevelopmentHistory()
        self.config = motion_config
        self.vla_budget = vla_budget
        self.memory = FailureMemory()
        self._contact_retry_references = {}
        self.revision = 0
        self.receipts: list[dict] = []
        self.details: list[dict] = []
        self.candidate_diagnostics: list[dict] = []
        self.held: str | None = None
        self.active: str | None = None
        self.grasp_reference = None
        self.payload_reference = None
        self.target_cache: dict = {}
        self.plans: dict = {}
        self.committed_grasps: dict = {}
        self.withdrawal_contact = None
        self.failed_contact_poses: dict = {}
        self.latest_request: dict | None = None
        self.preparation = measured_robot(self.p)
        self.gripper_command = -1. if self.preparation["gripper_opening_m"] >= .075 else 1.
        self.previous_scene = {}
        self._last_scene_changes = set()
        self._base_geometry = None
        self._screen_cache = {}
        self._instance_cache = {}
        self._self_filtered_capture = None
        self.instance_boundary_evidence = {}
        self._proprio_sample = None
        self.record_public_geometry = record_public_geometry
        self.precontact_instance_surface_v1 = precontact_instance_surface_v1
        self.legacy_chunk_boundaries_v1 = legacy_chunk_boundaries_v1
        self.compact_infeasible_candidates_v1 = compact_infeasible_candidates_v1
        self.prefix_consequence_workers = prefix_consequence_workers
        self.request_consequence_workers = request_consequence_workers
        self.public_geometry_evidence = {}
        self._last_free_chunk = None
        self.last_prefetch_adoption = None
        self._executing_prefix = None
        self.candidate_compaction = None

    def _record_public_geometry(self, name, points):
        """Keep exact measured screen inputs outside the model request."""
        if not self.record_public_geometry:
            return
        state = self.ex.toolkit._state
        if state.save(name+'.npz', points, step=state.latest_step) is None:
            raise RuntimeError('could not persist bounded public geometry')
        path = Path(state.artifact_path(name+'.npz', step=state.latest_step))
        self.public_geometry_evidence[name] = {'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'capture_step': state.latest_step, 'points': len(points),
            'source': 'public_rgbd_and_proprioceptive_robot_filter', 'private_truth_used': False}
        return self.public_geometry_evidence[name]

    def robot(self):
        state = measured_robot(self.p)
        step = self.p.env.execution_budget()["used_sim_steps"]
        velocity = None
        if self._proprio_sample is not None:
            previous_step, previous_position, previous_velocity = self._proprio_sample
            if step > previous_step:
                velocity = ((np.asarray(state["eef_xyz_m"])-previous_position)*self.config.hz/(step-previous_step)).tolist()
            elif step == previous_step:
                velocity = previous_velocity
        self._proprio_sample = step, np.asarray(state["eef_xyz_m"]), velocity
        return {key: state[key] for key in ("eef_xyz_m", "eef_quat_xyzw", "gripper_opening_m")} | {
            "held_anchor_id": self.held, "velocity_m_s": velocity}

    def holding_aperture(self, opening):
        """Exclude measured empty jaws without rejecting a thin held rim.

        Aperture only permits the RGB-D lift/coupling checks; it cannot prove
        a grasp. Reuse the registered original-task robot sensor calibration.
        """
        calibration = getattr(self.ex, 'grasp_measurement_calibration', None)
        if calibration is None:
            return .005 < opening < .075, {'source': 'legacy_uncalibrated_aperture_range',
                                          'opening_m': opening}
        limits = calibration['opening_calibration']
        lower = limits['closed_empty_max_m']+limits['tolerance_m']
        upper = limits['open_empty_min_m']-limits['tolerance_m']
        return lower < opening < upper, {'source': 'original_empty_gripper_proprioception',
            'opening_m': opening, 'empty_closed_upper_m': lower, 'empty_open_lower_m': upper,
            'calibration_source': calibration.get('source_report')}

    def refresh(self, *, contact_motion=None):
        self.ex.capture()
        association = {}
        if self.held is not None and self.payload_reference is not None:
            reference = self.payload_reference
            points = np.asarray(reference.get('target', [])).reshape(-1, 3)
            if len(points):
                before, after = reference['robot'], measured_robot(self.p)
                local = (points-before['eef_xyz_m'])@Rotation.from_quat(before['eef_quat_xyzw']).as_matrix()
                predicted = local@Rotation.from_quat(after['eef_quat_xyzw']).as_matrix().T+after['eef_xyz_m']
                association[self.held] = tuple(np.median(predicted, axis=0))
        if association:
            self.scene.refresh(sorted(self.scene.vocabulary), association_positions=association)
        else:
            self.scene.refresh(sorted(self.scene.vocabulary))
        self._base_geometry = None
        self._screen_cache.clear()
        self._instance_cache.clear()
        self._self_filtered_capture = None
        self.instance_boundary_evidence.clear()
        self.public_geometry_evidence.clear()
        # Requests publish a self-filtered held surface. Compare the same
        # measurement after capture; a raw SAM centre can differ by centimetres
        # even when neither the object nor the camera moved.
        self._refresh_held_measurement()
        current = {e.id: np.array(e.xyz) for e in self.scene.entities.values() if e.visible}
        changed = {key for key, value in current.items()
            if key not in self.previous_scene or np.linalg.norm(value-self.previous_scene[key]) > .01}
        registration = None
        contacts = {key: value for key, value in self._contact_retry_references.items() if key in changed}
        if contact_motion is not None:
            contacts[contact_motion[0]] = contact_motion
        for contact in contacts.values():
            key, axis, distance, reference, capture_step = contact
            # Partial masks can jump without the contacted object moving.
            # The same fresh depth fit used by the receipt determines whether
            # this source changed enough to unlock its contact retries.
            changed.discard(key)
            if self.ex.toolkit._state.latest_step > capture_step and not self.p.env.terminated:
                from robots.libero.bounded_payload import contact_axis_registration

                self._cloud_and_ik(key, contact=True)
                fit = contact_axis_registration(reference, self._base_geometry[0],
                    'xyz'.index(axis), distance, endpoint_tolerance_m=self.config.endpoint_tolerance_m)
                if contact_motion is not None and key == contact_motion[0]:
                    registration = fit
                if fit['accepted']:
                    low, high = fit['compatible_axis_interval_m']
                    if low > .01 or high < -.01:
                        changed.add(key)
                        self._contact_retry_references.pop(key, None)
        self._last_scene_changes = changed
        self.memory.tick(scene_changed=bool(changed), changed_anchors=changed)
        # Temporary occlusion does not erase the last measured pose. Merely
        # detecting the same stationary entity again is not scene progress.
        self.previous_scene.update(current)
        if self.held is None:
            # Retain the pre-grasp destination while the payload can obscure
            # it. Current RGB-D still supplies obstacles/collision surfaces;
            # a partial target mask must not move the planned release point.
            for e in self.scene.entities.values():
                if e.visible:
                    self.target_cache[e.id] = e
        return registration

    def _evidence(self, entity):
        return {"measurement_id": f"rgbd:{entity.source_step}:{entity.id}",
                "capture_step": int(entity.source_step), "source": "rgbd",
                "cameras": ["main", "wrist"] if self.scene.dual_view_fusion_v1 else ["main"],
                "operation": entity.geometry or "segmented_rgbd_bounds"}

    def _anchor_evidence(self, entity):
        evidence = [self._evidence(entity)]
        contact = self.plans.get(entity.id, {}).get('contact_evidence')
        if contact and contact['measurement_id'] != evidence[0]['measurement_id']:
            evidence.append(contact)
        return evidence

    def _has_anchor(self, entity):
        return entity is not None and (entity.visible
            or (entity.geometry and entity.geometry.startswith('cached_perception'))
            or (entity.id in self.target_cache and (entity.name in {'table', 'cabinet', 'stove', 'microwave'}
                or entity.name.startswith('area ') or entity.name.endswith('top surface')))
            or (entity.id == self.active and entity.id in self.committed_grasps))

    def anchors(self):
        anchors = []
        for current in self.scene.entities.values():
            if not self._has_anchor(current):
                continue
            cached = current.id in self.target_cache and (
                (self.held is not None and current.id != self.held) or not current.visible)
            e = self.target_cache[current.id] if cached else current
            anchors.append({"id": e.id, "label": e.name, "frame": "world",
                 "xyz_m": list(e.xyz), "size_m": (np.array(e.upper)-e.lower).tolist(),
                 "quat_xyzw": None, "confidence": float(self.scene._scores.get(e.id, 0.)),
                 "cached": cached or not e.visible or bool(e.geometry and e.geometry.startswith("cached_perception")),
                 "evidence": self._anchor_evidence(e)})
        return anchors

    def _cloud_and_ik(self, anchor_id=None, *, contact=False):
        robot = measured_robot(self.p)
        cache_key = (anchor_id, contact, self.held, tuple(robot["eef_xyz_m"]), tuple(robot['finger_positions_m']))
        if cache_key in self._screen_cache:
            return self._screen_cache[cache_key]
        hand_geometry = gripper_at_measured_fingers(self.geometry, robot['finger_positions_m'])
        if self._base_geometry is None:
            clouds = [np.asarray(self.ex.toolkit._state.load(name+"_world_high.npz")).reshape(-1, 3)
                      for name in ("agentview", "wrist")]
            # Preserve pixel identities until both selected and held masks
            # have been subtracted. A voxel centroid is not an instance pixel.
            cloud = np.concatenate(clouds)
            scene, _ = remove_current_gripper(cloud, robot["eef_xyz_m"], robot["eef_quat_xyzw"],
                                           hand_geometry, robot["gripper_opening_m"])
            ik = PublicPoseScreen(self.robot_xml, robot["joint_positions_rad"], robot["eef_xyz_m"],
                                 robot["eef_quat_xyzw"], self.geometry["site_offset_in_gripper_m"], warm_start=True)
            scene, _ = ik.remove_measured_arm(scene)
            scene, _ = remove_visual_robot(scene, ik)
            self._base_geometry = scene, ik
        scene, ik = self._base_geometry
        target = self._contact_pixels(anchor_id)
        if len(target):
            # A SAM mask can include the arm after approach. Apply the same
            # public self filter to that mask as to the scene; otherwise our
            # own palm pixels become a fictitious target/palm collision.
            target, _ = remove_current_gripper(target, robot["eef_xyz_m"], robot["eef_quat_xyzw"],
                hand_geometry, robot["gripper_opening_m"])
            target, _ = ik.remove_measured_arm(target)
            target, _ = remove_visual_robot(target, ik)
        payload = []
        held_cloud = np.empty((0, 3))
        if self.held:
            held_cloud = self._instance_pixels(self.held)
            if len(held_cloud):
                held_cloud, _ = remove_current_gripper(held_cloud, robot['eef_xyz_m'], robot['eef_quat_xyzw'],
                    hand_geometry, robot['gripper_opening_m'])
                held_cloud, _ = ik.remove_measured_arm(held_cloud)
                held_cloud, _ = remove_visual_robot(held_cloud, ik)
                if len(target):
                    from scipy.spatial import cKDTree
                    # Independent SAM queries can share depth pixels. A
                    # verified moving payload cannot also remain part of a
                    # stationary destination's collision surface.
                    shared = cKDTree(held_cloud).query(target,
                        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                    target = target[~shared]
        # Subtract both instances in one pass, before separate_target_points
        # downsamples the remaining obstacles. Otherwise the first subtraction
        # voxelises held pixels and the second can no longer recognise them.
        measured_scene, measured_target = scene, target
        _, scene = separate_target_points(np.concatenate([target, held_cloud]), scene)
        from robots.libero.v5_geometric_grasp import _voxel
        # A verified held instance moves with the hand. Checking its current
        # pixels again as a stationary contact target makes a braking palm
        # collide with the object's old location. Its surface is already
        # represented by the moving payload below.
        target = np.empty((0, 3)) if anchor_id == self.held else _voxel(target, .002)
        if len(held_cloud):
            payload = (_voxel(held_cloud, .002)-robot["eef_xyz_m"])@Rotation.from_quat(robot["eef_quat_xyzw"]).as_matrix()
        screen = PublicRouteScreen(scene, hand_geometry, ik, opening=robot["gripper_opening_m"],
            contact_points=target, contact_allowed=contact, payload_local=payload,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']},
            measured_scene_points=measured_scene, measured_target_points=measured_target)
        if self.record_public_geometry:
            name = f'bounded_screen_{anchor_id}_{int(contact)}'
            self._record_public_geometry(name+'_scene', screen.points)
            self._record_public_geometry(name+'_target', screen.target)
            self._record_public_geometry(name+'_payload_local', screen.payload)
        self._screen_cache[cache_key] = screen
        return screen

    def _self_filtered_world(self, world):
        """Keep exact current pixels present in the public route's scene."""
        if self._base_geometry is None:
            return world
        from scipy.spatial import cKDTree

        # The raw self-filtered scene is immutable for this capture. Several
        # contact/instance fits query the same full camera frame; reuse only
        # identical pixel bytes, never a previous frame or different geometry.
        scene = self._base_geometry[0]
        capture_step = self.ex.toolkit._state.latest_step
        cache = self._self_filtered_capture
        if cache is None or cache['scene'] is not scene or cache['step'] != capture_step:
            cache = self._self_filtered_capture = {'scene': scene, 'step': capture_step, 'frames': {}}
        key = (world.shape, world.dtype.str, hashlib.sha256(world.tobytes()).digest())
        if key in cache['frames']:
            return cache['frames'][key].copy()
        flat = world.reshape(-1, 3)
        ids = np.flatnonzero(np.isfinite(flat).all(axis=1))
        current = cKDTree(scene).query(flat[ids],
            distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
        filtered = np.full_like(flat, np.nan)
        filtered[ids[current]] = flat[ids[current]]
        filtered = filtered.reshape(world.shape)
        cache['frames'][key] = filtered
        return filtered.copy()

    def _handle_pixels(self, measurement, *, contact_surface=False):
        """Load only the current public handle samples, never a pose prior."""
        if (not measurement or measurement.get('source_step') is None
                or measurement['source_step'] != self.ex.toolkit._state.latest_step):
            return np.empty((0, 3))
        return self._stored_handle_pixels(measurement, contact_surface=contact_surface)

    @staticmethod
    def _stored_handle_pixels(measurement, *, contact_surface=False):
        clouds = []
        for view in measurement.get('views', {}).values():
            info = (view.get('contact_cloud') or view.get('cloud')) if contact_surface else view.get('cloud')
            if (view.get('pose') and info and info.get('source') == 'perception'
                    and info.get('source_step') == measurement['source_step']):
                with np.load(info['path']) as stored:
                    clouds.append(np.asarray(stored[stored.files[0]]).reshape(-1, 3))
        return np.concatenate(clouds) if clouds else np.empty((0, 3))

    def _exclude_measured_support(self, pixels):
        """Keep a currently measured support plane in the obstacle cloud."""
        if not len(pixels):
            return pixels, None
        state = self.ex.toolkit._state
        cache_key = ('support_plane', state.latest_step)
        if cache_key not in self._instance_cache:
            from robots.libero.v5_perception_geometry import measured_work_surface

            anchors = [e for e in self.scene.entities.values()
                if e.visible and not e.part_of and not fixture_actions(e.name)]
            surface = None
            for camera in ('agentview', 'wrist'):
                world = self._self_filtered_world(np.asarray(state.load(camera+'_world_high.npz')))
                surface = measured_work_surface(world, anchors)
                if surface is not None:
                    surface = {**surface, 'camera': camera, 'source_step': state.latest_step}
                    break
            self._instance_cache[cache_key] = surface
        surface = self._instance_cache[cache_key]
        if surface is None or surface['normal_residual_p95_m'] > .001:
            return pixels, None
        distance = abs((pixels-np.asarray(surface['centroid_xyz']))@np.asarray(surface['normal_xyz']))
        support = distance <= .001
        return pixels[~support], {'source': 'current_rgbd_measured_support_plane',
            'measurement': surface, 'surface_residual_m': .001,
            'retained_as_obstacles': int(support.sum()), 'private_pose_used': False}

    def _contact_pixels(self, anchor_id, *, handle_only=False):
        pixels = self._instance_pixels(anchor_id)
        committed = self.committed_grasps.get(anchor_id, {})
        if not committed and self.withdrawal_contact and self.withdrawal_contact['anchor_id'] == anchor_id:
            committed = self.withdrawal_contact
        withdrawal = committed.get('withdrawal_surface') if committed is self.withdrawal_contact else None
        if withdrawal is not None and self.active is None:
            # The fixture may have moved since approach and disappeared from
            # SAM during release. Match CURRENT pixels to its last measured
            # contact surface, without attaching it to the departing hand.
            for camera in ('agentview', 'wrist'):
                world = self._self_filtered_world(np.asarray(
                    self.ex.toolkit._state.load(camera+'_world_high.npz')))
                recovered, evidence = complete_contact_surface(world, withdrawal['xyz_world'])
                pixels = np.concatenate([pixels, world[recovered]])
                self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                    **evidence, 'camera': camera,
                    'source': 'current_rgbd_matches_last_contact_before_release',
                    'reference_capture_step': withdrawal['source_step'],
                    'capture_step': self.ex.toolkit._state.latest_step})
        plan = self.plans.get(anchor_id, committed.get('plan', {}))
        surface = plan.get('surface_measurement')
        entity = self.scene.entities.get(anchor_id)
        reference = committed.get('instance_reference')
        if (reference is not None and self.active == anchor_id and self.held is None
                and entity is not None and entity.visible and self._base_geometry is not None):
            cache_key = (anchor_id, 'precontact_surface')
            if cache_key not in self._instance_cache:
                from scipy.spatial import cKDTree

                from robots.libero.bounded_payload import _surface_registration

                old = np.asarray(reference['xyz_world'])
                # Finger contact can move the object before lift. Register
                # its old measured surface to the current clean instance;
                # never infer this displacement from commanded hand motion.
                stationary = reference.get('stationary_scene')
                registration = {'accepted': False, 'reason': 'precontact_stationary_scene_missing'}
                if stationary is not None:
                    old, registration = _surface_registration(old, pixels, reciprocal=True)
                overlap = cKDTree(old).query(pixels,
                    distance_upper_bound=np.nextafter(.001, np.inf))[0] <= .001
                recovered, evidence = [pixels], []
                # A visible-surface centre can jump under finger occlusion.
                # Require shared current depth, rather than centre proximity,
                # before the old surface can establish contact identity.
                if overlap.sum() >= 40:
                    lower, upper = old.min(0)-.001, old.max(0)+.001
                    current_views = []
                    for camera in ('agentview', 'wrist'):
                        world = self._self_filtered_world(np.asarray(
                            self.ex.toolkit._state.load(camera+'_world_high.npz')))
                        current_views.append(world.reshape(-1, 3))
                        member, detail = complete_contact_surface(world, old, current_boundary=True)
                        extent = ((world >= lower).all(axis=2) & (world <= upper).all(axis=2))
                        # A current rim can lie just beyond the precontact
                        # extent. Recover one measured two-axis plane edge
                        # after clipping; do not reinstate the unrestricted
                        # continuation outside that old extent.
                        member, local_plane = complete_planar_boundary(world, member & extent)
                        recovered.append(world[member])
                        evidence.append({'camera': camera,
                            'post_extent_current_local_plane': local_plane, **detail})
                    _, axes = np.linalg.eigh(np.cov(old.T))
                    scene = self._base_geometry[0]
                    member, curved = complete_cylindrical_contact_surface(scene.reshape(-1, 1, 3), old, axes[:, -1])
                    extent = ((scene >= lower).all(axis=1) & (scene <= upper).all(axis=1))
                    recovered.append(scene[member[:, 0] & extent])
                    evidence.append({'source': 'current_rgbd_matches_precontact_circular_sections',
                        'fit': curved, 'axis_xyz': axes[:, -1].tolist()})
                    if stationary is not None:
                        from robots.libero.bounded_payload import (
                            complete_spatial_payload_component,
                        )

                        # A curved rim can connect to the current instance
                        # through several pixels without fitting one plane
                        # or the old partial-view circular axis. Reuse the
                        # measured 3mm graph, bounded by the contact surface
                        # and with the same 4mm stationary-scene veto.
                        current = np.concatenate(current_views)
                        member, connected = complete_spatial_payload_component(
                            current, pixels, stationary, lower, upper)
                        recovered.append(current[member])
                        evidence.append(connected)
                recovered = np.concatenate(recovered)
                retained = 0
                if stationary is not None and len(stationary):
                    # A small surface fit can otherwise sweep a curved
                    # boundary onto its unmoved support or neighbour. Keep
                    # those additions in the obstacle cloud, as after lift.
                    added = cKDTree(pixels).query(recovered)[0] > 1e-6
                    static = cKDTree(stationary).query(recovered,
                        distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
                    retained = int((added & static).sum())
                    recovered = recovered[~(added & static)]
                pixels, support = self._exclude_measured_support(recovered)
                self._instance_cache[cache_key] = pixels
                self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                    'source': 'current_rgbd_matches_exact_precontact_instance_surface',
                    'reference_capture_step': reference['source_step'],
                    'capture_step': self.ex.toolkit._state.latest_step,
                    'shared_current_pixels': int(overlap.sum()), 'minimum_shared_pixels': 40,
                    'surface_registration': registration,
                    'stationary_pixels_retained_as_obstacles': retained,
                    'measured_support': support,
                    'surface_residual_m': .001, 'private_pose_used': False, 'matches': evidence})
            pixels = self._instance_cache[cache_key]
        if (surface and 'anchor_xyz' in committed and self.active is None and entity is not None
                and measured_robot(self.p)['gripper_opening_m'] >= .075
                and np.linalg.norm(np.asarray(entity.xyz)-committed['anchor_xyz']) <= .01):
            # Approaching can hide a panel edge before fingertip contact.
            # Retain its original measured extent, but recover only current
            # depth components connected to that measured surface. A curved
            # rim need not satisfy the flat-face extrapolation model.
            reference_points = np.asarray(surface['xyz_world'])
            for camera in ('agentview', 'wrist'):
                world = self._self_filtered_world(np.asarray(
                    self.ex.toolkit._state.load(camera+'_world_high.npz')))
                matched, evidence = complete_contact_surface(world, reference_points)
                valid = (np.isfinite(world).all(axis=2)
                    & (world >= reference_points.min(0)).all(axis=2)
                    & (world <= reference_points.max(0)).all(axis=2))
                labels, _ = depth_components(world, valid, max_gap_m=.003)
                supported = np.unique(labels[matched & valid])
                recovered = (labels >= 0) & np.isin(labels, supported)
                pixels = np.concatenate([pixels, world[recovered]])
                self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                    'camera': camera, 'source': 'current_rgbd_component_of_committed_precontact_surface',
                    'reference_capture_step': surface['source_step'],
                    'capture_step': self.ex.toolkit._state.latest_step,
                    'max_gap_m': .003, 'recovered_pixels': int(recovered.sum()), **evidence})
        if surface and self.active == anchor_id:
            # Surface contact does not imply attachment to the EEF. Recover
            # only current depth samples matching the previously measured
            # stationary surface; never translate it with gripper motion.
            for camera in ('agentview', 'wrist'):
                world = self._self_filtered_world(np.asarray(
                    self.ex.toolkit._state.load(camera+'_world_high.npz')))
                recovered, evidence = complete_contact_surface(world, surface['xyz_world'])
                pixels = np.concatenate([pixels, world[recovered]])
                self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                    'camera': camera, 'source': 'current_rgbd_matches_contacted_surface',
                    'reference_capture_step': surface['source_step'],
                    'capture_step': self.ex.toolkit._state.latest_step, **evidence})
            # Closing or pushing can expose a surface absent from the old
            # contact capture. Use current measured instance pixels as well
            # as the stationary reference matches to seed its current edge.
            # Robot-filtered gaps and depth discontinuities cannot bridge.
            current_surface = pixels
            for camera in ('agentview', 'wrist'):
                world = self._self_filtered_world(np.asarray(
                    self.ex.toolkit._state.load(camera+'_world_high.npz')))
                recovered, evidence = complete_contact_surface(world, current_surface, current_boundary=True)
                pixels = np.concatenate([pixels, world[recovered]])
                self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                    'camera': camera, 'source': 'current_rgbd_boundary_of_contacted_surface',
                    'reference_capture_step': surface['source_step'],
                    'capture_step': self.ex.toolkit._state.latest_step, **evidence})
        measured = plan.get('handle_measurement')
        if measured:
            current = self._handle_pixels(measured, contact_surface=True)
            if len(current) and any(view.get('contact_cloud') for view in measured.get('views', {}).values()):
                # A current control can be segmented in only one camera.
                # Recover matching current pixels in both views before the
                # scene is voxelised. Keep the existing 1 mm surface and
                # depth-continuity tests, with robot pixels already removed.
                recovered = [current]
                for camera in ('agentview', 'wrist'):
                    world = self._self_filtered_world(np.asarray(
                        self.ex.toolkit._state.load(camera+'_world_high.npz')))
                    matched, evidence = complete_contact_surface(world, current)
                    recovered.append(world[matched])
                    self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                        'camera': camera, 'source': 'current_rgbd_matches_current_handle_surface',
                        'capture_step': self.ex.toolkit._state.latest_step, **evidence})
                current = np.concatenate(recovered)
            rolling_surface = committed.get('contact_surface_reference')
            reference = rolling_surface['robot'] if rolling_surface else committed.get('contact_robot')
            entity = self.scene.entities.get(anchor_id)
            if (not len(current) and reference is None and committed and self.active is None
                    and measured_robot(self.p)['gripper_opening_m'] >= .075 and entity is not None
                    and np.linalg.norm(np.asarray(entity.xyz)-committed['anchor_xyz']) <= .01):
                # Approach/alignment refreshes the cameras before contact.
                # Keep stationary handle identity only where CURRENT depth
                # matches its measured old surface, inside its old extent.
                recovered = []
                for camera in ('agentview', 'wrist'):
                    world = self._self_filtered_world(np.asarray(
                        self.ex.toolkit._state.load(camera+'_world_high.npz')))
                    mask, evidence = complete_contact_surface(world,
                        self._stored_handle_pixels(measured, contact_surface=True))
                    recovered.append(world[mask])
                    self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                        'camera': camera, 'source': 'current_rgbd_matches_committed_precontact_handle',
                        'reference_capture_step': measured['source_step'],
                        'capture_step': self.ex.toolkit._state.latest_step, **evidence})
                current = np.concatenate(recovered)
            if (reference is not None and self.active == anchor_id
                    and measured_robot(self.p)['gripper_opening_m'] < .075):
                # Only CURRENT pixels within 1 mm of the last measured
                # handle surface can regain contact membership. The stored
                # cloud itself is never subtracted from current obstacles.
                # Use public EEF displacement to track a contacted handle;
                # unrelated adjacent/depth-discontinuous surfaces stay out.
                # A partial current mask must not erase the still-measured
                # opposite side of the committed handle. Track that original
                # surface, supplementing (rather than replacing) current IDs.
                tracked = committed.get('plan', {}).get('handle_measurement', measured)
                old = (np.asarray(rolling_surface['xyz_world']) if rolling_surface
                    else self._stored_handle_pixels(tracked, contact_surface=True))
                robot = measured_robot(self.p)
                if len(old):
                    old_rotation = Rotation.from_quat(reference['eef_quat_xyzw']).as_matrix()
                    rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix()
                    predicted = ((old-reference['eef_xyz_m'])@old_rotation)@rotation.T+robot['eef_xyz_m']
                    registration = None
                    if self._base_geometry is not None:
                        from robots.libero.bounded_payload import (
                            _surface_registration,
                            contact_normal_registration,
                        )

                        # The grasped handle can deflect relative to the
                        # fingers. Refine the EEF prediction using current,
                        # self-filtered depth near that measured surface.
                        # Registration still enforces its existing overlap,
                        # residual-improvement and 15 mm displacement gates.
                        scene = self._base_geometry[0]
                        local = scene[((scene >= predicted.min(0)-.015)
                            & (scene <= predicted.max(0)+.015)).all(axis=1)]
                        predicted, registration = _surface_registration(predicted, local)
                        normal = tracked.get('pose', {}).get('approach_normal_xyz')
                        if (not registration.get('accepted') and normal is not None
                                and registration.get('reason') == 'surface_shift_exceeds_public_hold_tolerance'):
                            # An unconstrained fit can slide along an occluded
                            # handle. Refit only its independently measured
                            # normal, retaining the same displacement gates.
                            normal = rotation@old_rotation.T@np.asarray(normal)
                            predicted, normal_fit = contact_normal_registration(predicted, local, normal)
                            registration = {**normal_fit, 'rigid_fit': registration}
                    recovered, records = [current], []
                    for camera in ('agentview', 'wrist'):
                        world = np.asarray(self.ex.toolkit._state.load(camera+'_world_high.npz'))
                        world = self._self_filtered_world(world)
                        # A handle touches its backing surface. Local depth
                        # continuity alone can therefore grow through the
                        # attachment onto the door, cabinet or even table.
                        # Retain only CURRENT depth supported by the tracked
                        # measured handle extent; a new silhouette requires
                        # an independent current handle measurement above.
                        extended, boundary = complete_contact_surface(world, predicted)
                        recovered.append(world[extended])
                        records.append({'camera': camera, 'source': 'current_rgbd_matches_contacted_handle_surface',
                            'reference_capture_step': (rolling_surface['source_step'] if rolling_surface
                                else tracked['source_step']),
                            'capture_step': self.ex.toolkit._state.latest_step,
                            'registration': registration,
                            'boundary': boundary, 'private_pose_used': False})
                    current = np.concatenate(recovered)
                    if len(current):
                        from scipy.spatial import cKDTree

                        # One current view can expose a handle surface absent
                        # from the pre-contact view. Associate the other view
                        # to those measured current pixels at the same 1 mm
                        # residual; do not expand a box or substitute the old
                        # predicted surface for present depth measurements.
                        tree = cKDTree(current)
                        extent = np.concatenate([predicted, self._handle_pixels(measured, contact_surface=True)])
                        lower, upper = extent.min(0)-.001, extent.max(0)+.001
                        for camera in ('agentview', 'wrist'):
                            world = self._self_filtered_world(np.asarray(
                                self.ex.toolkit._state.load(camera+'_world_high.npz')))
                            flat = world.reshape(-1, 3)
                            valid = (np.isfinite(flat).all(axis=1)
                                & (flat >= lower).all(axis=1) & (flat <= upper).all(axis=1))
                            ids = np.flatnonzero(valid)
                            matched = ids[tree.query(flat[ids],
                                distance_upper_bound=np.nextafter(.001, np.inf))[0] <= .001]
                            recovered.append(flat[matched])
                            records.append({'camera': camera,
                                'source': 'current_rgbd_matches_other_current_contact_pixels',
                                'capture_step': self.ex.toolkit._state.latest_step,
                                'surface_residual_m': .001, 'matched_pixels': len(matched),
                                'private_pose_used': False})
                        current = np.concatenate(recovered)
                    tangent, axis_evidence = measured_handle_axis(old)
                    if tangent is not None and len(current) >= 40:
                        # A bar's newly exposed curved side is not coplanar
                        # with its old visible side. Current measured arcs,
                        # along the measured handle axis, can own those raw
                        # depth pixels without carving a proximity halo.
                        # The backing plane's horizontal tangent is not the
                        # long axis of a vertical handle. Use the segmented
                        # handle's measured 3D axis, with the same public
                        # EEF transform used for its contact surface.
                        axis = rotation@old_rotation.T@tangent
                        curved = [current]
                        for camera in ('agentview','wrist'):
                            world = self._self_filtered_world(np.asarray(
                                self.ex.toolkit._state.load(camera+'_world_high.npz')))
                            member, cylinder = complete_cylindrical_contact_surface(world,current,axis)
                            curved.append(world[member])
                            records.append({'camera':camera,'capture_step':self.ex.toolkit._state.latest_step,
                                'handle_axis_measurement': axis_evidence, **cylinder})
                        current = np.concatenate(curved)
                    self.instance_boundary_evidence.setdefault(anchor_id, []).extend(records)
            if handle_only:
                return current
            pixels = np.concatenate([pixels, current])
        return np.empty((0, 3)) if handle_only else pixels

    def _guided_payload_pixels(self, world, semantic_mask, camera, entity, current_points):
        """Refine a currently measured instance with an interior SAM point."""
        from scipy.ndimage import distance_transform_edt

        from rpent.robots.components.sam3_client import Sam3Client

        empty = np.empty((0, 3))
        evidence = {'source': 'current_measured_instance_interior_point_sam',
            'camera': camera, 'capture_step': self.ex.toolkit._state.latest_step,
            'private_pose_used': False, 'member_pixels': 0}
        rpc = getattr(self.scene, 'rpc', None)
        if rpc is None or semantic_mask is None:
            return empty, {**evidence, 'reason': 'current_mask_or_segment_service_unavailable'}
        current = np.asarray(current_points).reshape(-1, 3)
        current = current[np.isfinite(current).all(axis=1)]
        if not len(current):
            return empty, {**evidence, 'reason': 'no_current_instance_depth_seed'}
        # A robust anchor truncates measured tails (e.g. a bowl's upper rim).
        # Collision membership needs the complete currently owned raw extent;
        # these bounds still cannot grant membership without a SAM mask.
        lower, upper = current.min(0), current.max(0)
        valid = (np.isfinite(world).all(axis=2)
            & (world >= lower).all(axis=2) & (world <= upper).all(axis=2))
        interior = np.asarray(semantic_mask, bool) & valid
        if not interior.any():
            return empty, {**evidence, 'reason': 'no_current_instance_depth_seed'}
        point = list(map(int, np.unravel_index(
            np.argmax(distance_transform_edt(interior)), interior.shape)))
        evidence['point_row_col'] = point
        evidence['prompt_surface_bounds_m'] = [lower.tolist(), upper.tolist()]
        image = self.ex.toolkit._state.load_bytes(camera+'_high.png')
        reply = rpc.call('sam3.segment', kwargs={
            'image_base64': base64.b64encode(image).decode('ascii'),
            'point': point, 'min_score': .35}, timeout_s=120)
        self.scene.calls += 1
        result = Sam3Client._decode_result(reply)
        if not result.found:
            return empty, {**evidence, 'reason': result.reason}
        if result.mask.shape != interior.shape or not result.mask[tuple(point)]:
            return empty, {**evidence, 'reason': 'guided_mask_does_not_match_current_seed'}
        mask = result.mask & valid
        if (result.mask & ~valid).any():
            # The prompt extent selects an interior seed, not the final
            # object's silhouette. A new SAM tail must connect to already
            # owned mask pixels through current self-filtered depth. A
            # disconnected neighbour or the robot cannot extend the fit.
            filtered = self._self_filtered_world(world)
            labels, _ = depth_components(filtered,
                result.mask & np.isfinite(filtered).all(axis=2), max_gap_m=.003)
            supported = np.unique(labels[mask])
            mask |= (labels >= 0) & np.isin(labels, supported)
        evidence.update(score=result.score, member_pixels=int(mask.sum()),
            semantic_recall=float((mask & interior).sum()/interior.sum()),
            depth_connected_pixels_outside_prompt_extent=int((mask & ~valid).sum()))
        evidence['artifact'] = self._record_public_geometry(
            f'bounded_payload_guided_{entity.id}_{camera}', world[mask])
        return world[mask], evidence

    def _instance_pixels(self, anchor_id):
        # Fusion stores voxel CENTROIDS. They are geometry estimates, not
        # original depth pixels; exact pixel-identity subtraction using them
        # leaves the object itself in the obstacle cloud. Use preserved
        # per-camera samples to remove only measured instance members.
        if anchor_id in self._instance_cache:
            return self._instance_cache[anchor_id]
        views = getattr(self.scene, 'measurement_clouds_by_view', {}).get(anchor_id, {})
        samples, records, current_views, semantic_masks = {}, [], {}, {}
        entity = self.scene.entities.get(anchor_id)
        clean_instance = (entity is not None and not entity.part_of
            and not fixture_actions(entity.name))
        for camera, view in views.items():
            if view.get('xyz_world') is None:
                continue
            if (anchor_id == self.held and self.payload_reference is not None
                    and view.get('source_step') is not None
                    and view['source_step'] != self.ex.toolkit._state.latest_step):
                continue
            points = np.asarray(view['xyz_world']).reshape(-1, 3)
            # Recover only omitted pixels supported by a continuous measured
            # instance surface. Never carve a metric halo around the target:
            # a neighbouring obstacle may be only millimetres away.
            if view.get('source_step') is not None and view['source_step'] == self.ex.toolkit._state.latest_step:
                from scipy.spatial import cKDTree
                world = np.asarray(self.ex.toolkit._state.load(camera+'_world_high.npz'))
                refine_fixture = (entity is not None and entity.part_of and anchor_id == self.active
                    and measured_robot(self.p)['gripper_opening_m'] < .075)
                if refine_fixture or clean_instance:
                    world = self._self_filtered_world(world)
                flat = world.reshape(-1, 3)
                near = (np.isfinite(flat).all(axis=1)
                    & ((flat >= points.min(0)-1e-6) & (flat <= points.max(0)+1e-6)).all(axis=1))
                mask = np.zeros(len(flat), bool)
                mask[near] = cKDTree(points).query(flat[near],
                    distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                original = mask.reshape(world.shape[:2])
                semantic_masks[camera] = original.copy()
                component = None
                if clean_instance:
                    entity = self.scene.entities[anchor_id]
                    # An object's SAM mask can retain disconnected tabletop
                    # pixels before contact too. Those remain obstacles.
                    # Keep the depth component supported by this capture's
                    # measured object bounds before constructing its hull.
                    original, component = clean_object_mask(world, original,
                        prior_lower=entity.lower, prior_upper=entity.upper)
                expanded, evidence = complete_instance_boundary(world, original,
                    rounds=sum(original.shape) if refine_fixture else 3)
                expanded, planar = complete_planar_boundary(world, expanded)
                sparse = None
                if clean_instance:
                    # A grazing face can have >3 mm pixel spacing. Recover
                    # tangent-supported holes inside its measured extent;
                    # do not extend the instance into its support plane.
                    measured, sparse = complete_sparse_instance_boundary(world, original)
                    expanded |= measured
                connected = None
                if clean_instance and original.any():
                    # A curved handle seam need not have a linear tangent.
                    # Recover its current depth component only inside the
                    # clean mask's measured extent; a table below that extent
                    # or a disconnected neighbour remains an obstacle.
                    measured = world[original]
                    lower, upper = measured.min(0), measured.max(0)
                    valid = (np.isfinite(world).all(axis=2)
                        & (world >= lower).all(axis=2) & (world <= upper).all(axis=2))
                    labels, _ = depth_components(world, valid, max_gap_m=.003)
                    supported = np.unique(labels[expanded & valid])
                    members = (labels >= 0) & np.isin(labels, supported)
                    connected = {'source': 'current_self_filtered_rgbd_component_within_clean_mask_extent',
                        'max_gap_m': .003, 'lower': lower.tolist(), 'upper': upper.tolist(),
                        'added_pixels': int((members & ~expanded).sum())}
                    expanded |= members
                refined_component = None
                if clean_instance:
                    expanded, refined_component = clean_object_mask(world, expanded,
                        prior_lower=entity.lower, prior_upper=entity.upper)
                records.append({'camera': camera, 'source_step': view['source_step'],
                    'held_component': component, 'refined_component': refined_component,
                    'local_plane': planar, 'sparse_boundary': sparse,
                    'connected_surface': connected, **evidence})
                points = world[expanded]
                current_views[camera] = world, expanded
            samples[camera] = points
        if clean_instance and len(current_views) == 2:
            # One camera can observe a rim hidden behind the fingers in the
            # other. Its current measured extent can bound same-view depth
            # continuity without requiring an occluded opposite projection.
            # Retain the 3 mm component test and the public self filter;
            # a bounding box alone never establishes pixel ownership.
            measured = np.concatenate([world[mask] for world, mask in current_views.values()])
            if len(measured):
                lower, upper = measured.min(0), measured.max(0)
                for camera, (world, mask) in list(current_views.items()):
                    valid = (np.isfinite(world).all(axis=2)
                        & (world >= lower).all(axis=2) & (world <= upper).all(axis=2))
                    labels, _ = depth_components(world, valid, max_gap_m=.003)
                    supported = np.unique(labels[mask & valid])
                    completed = mask | ((labels >= 0) & np.isin(labels, supported))
                    current_views[camera] = world, completed
                    samples[camera] = world[completed]
                    next(row for row in records if row['camera'] == camera)['fused_extent_component'] = {
                        'source': 'current_self_filtered_rgbd_component_within_two_current_mask_extents',
                        'max_gap_m': .003, 'lower': lower.tolist(), 'upper': upper.tolist(),
                        'added_pixels': int((completed & ~mask).sum())}
        if len(current_views) == 2:
            for camera, (world, mask) in current_views.items():
                other = next(key for key in current_views if key != camera)
                other_world, other_mask = current_views[other]
                metadata = self.ex.toolkit._state.load(other+'_metadata.json')
                completed, evidence = complete_crossview_boundary(world, mask, other_world, other_mask, metadata)
                if clean_instance:
                    completed, component = clean_object_mask(world, completed,
                        prior_lower=entity.lower, prior_upper=entity.upper)
                    evidence['refined_component'] = component
                    # The local surface test is independent current evidence
                    # for a fragment whose small size triggered cleanup.
                    # Retain it after cleanup instead of deleting it again.
                    completed, semantic = retain_crossview_semantic_fragments(world,
                        semantic_masks[camera], completed, other_world, other_mask)
                    evidence['semantic_fragments'] = semantic
                samples[camera] = world[completed]
                next(row for row in records if row['camera'] == camera)['crossview'] = evidence
        entity = self.scene.entities.get(anchor_id)
        if entity is not None and (entity.part_of or clean_instance) and samples:
            # SAM may identify a surface in only one camera even while its
            # depth is visible in both. Recover the other view only from
            # current surface matches, projected identity and depth support;
            # an entity's bounding box alone cannot establish membership.
            current_samples = [points for camera, points in samples.items()
                if views[camera].get('source_step') is not None
                and views[camera]['source_step'] == self.ex.toolkit._state.latest_step]
            if current_samples:
                surface = np.concatenate(current_samples)
                for camera in ('agentview', 'wrist'):
                    if camera in samples:
                        continue
                    world = self._self_filtered_world(np.asarray(
                        self.ex.toolkit._state.load(camera+'_world_high.npz')))
                    completed, evidence = complete_contact_surface(world, surface)
                    if not completed.any():
                        continue
                    crossviews = []
                    for other, (other_world, other_mask) in current_views.items():
                        metadata = self.ex.toolkit._state.load(other+'_metadata.json')
                        completed, crossview = complete_crossview_boundary(world, completed,
                            other_world, other_mask, metadata)
                        crossviews.append({'camera': other, **crossview})
                    samples[camera] = world[completed]
                    records.append({'camera': camera, 'source_step': self.ex.toolkit._state.latest_step,
                        'source': 'current_rgbd_matches_current_measured_instance_surface',
                        'crossviews': crossviews, **evidence})
        if samples:
            result = np.concatenate(list(samples.values()))
        elif anchor_id == self.held and self.payload_reference is not None:
            result = np.empty((0, 3))
        else:
            result = self.scene.measurement_clouds.get(anchor_id, np.empty((0, 3)))
        if clean_instance and current_views and len(result):
            result, support = self._exclude_measured_support(result)
            if support is not None:
                records.append({'source': 'instance_support_plane_exclusion',
                    'measurement': support, 'private_pose_used': False})
        if anchor_id == self.held and self.payload_reference is not None and self._base_geometry is not None:
            from scipy.spatial import cKDTree

            from robots.libero.bounded_payload import (
                complete_moving_boundary,
                complete_spatial_payload_component,
                moving_payload_pixels,
            )
            scene = self._base_geometry[0]
            # SAM can include the fingers or palm. Registration must see the
            # same robot-filtered raw pixels as collision screening, or it
            # tries to fit the moving hand as part of the held object.
            stationary = cKDTree(self.payload_reference['scene']).query(result,
                distance_upper_bound=np.nextafter(.004, np.inf))[0] <= .004
            # A current semantic mask can bleed onto the destination rim.
            # Apply the same pre-lift static-scene veto to those original
            # pixels as to temporal/boundary additions before registration.
            records.append({'source': 'pre_lift_stationary_scene_veto_current_mask',
                'stationary_pixels_retained_as_obstacles': int(stationary.sum()),
                'stationary_residual_m': .004})
            result = result[~stationary]
            current_tree = cKDTree(scene)
            present = current_tree.query(result,
                distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
            semantic = [world[semantic_masks[camera]] for camera, (world, _) in current_views.items()
                        if camera in semantic_masks]
            member, temporal = moving_payload_pixels(scene, self.payload_reference, measured_robot(self.p),
                current_target=result[present],
                current_semantic_target=np.concatenate(semantic) if semantic else None)
            boundary_seeds = np.concatenate([result[present], scene[member]])
            result = np.concatenate([result, scene[member]])
            records.append(temporal)
            # A held surface can remain visible to depth after SAM loses
            # that view. Its current co-moving pixels still seed boundary
            # refinement; requiring a semantic mask discards this evidence.
            for camera in ('agentview', 'wrist'):
                if camera not in current_views:
                    world = np.asarray(self.ex.toolkit._state.load(camera+'_world_high.npz'))
                    current_views[camera] = world, np.zeros(world.shape[:2], bool)
            for camera, (world, mask) in current_views.items():
                # Boundary membership uses the same current self-filtered
                # scene as the route screen. Robot pixels cannot bridge two
                # otherwise disconnected measured surfaces.
                flat = world.reshape(-1, 3)
                eligible = np.isfinite(flat).all(axis=1)
                ids = np.flatnonzero(eligible)
                present = current_tree.query(flat[ids],
                    distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                filtered = np.full_like(flat, np.nan)
                filtered[ids[present]] = flat[ids[present]]
                filtered = filtered.reshape(world.shape)
                valid = np.isfinite(filtered).all(axis=2)
                completed, evidence = complete_moving_boundary(filtered, mask & valid, boundary_seeds,
                    self.payload_reference['scene'], surface_extent=temporal.get('measured_surface_extent_m'),
                    rgb=self.ex.toolkit._state.load(camera+'_high.png'),
                    semantic_mask=semantic_masks.get(camera))
                result = np.concatenate([result, world[completed & ~mask]])
                records.append({'camera': camera, **evidence})
            if entity is not None and len(result):
                seeds = [result]
                for camera, (world, _) in current_views.items():
                    guided, evidence = self._guided_payload_pixels(
                        world, semantic_masks.get(camera), camera, entity, result)
                    if len(guided):
                        # SAM can supply a missing interior seed after the
                        # first boundary pass. Let depth and silhouette
                        # support converge on these same public pixels.
                        moving = np.concatenate([result, guided])
                        completed, continuation = complete_moving_boundary(
                            world, np.zeros(world.shape[:2], bool), moving,
                            self.payload_reference['scene'],
                            # Preserve the measured association interval;
                            # sampled extrema are not exact object edges.
                            surface_extent=[moving.min(0)-temporal['surface_residual_m'],
                                            moving.max(0)+temporal['surface_residual_m']],
                            rgb=self.ex.toolkit._state.load(camera+'_high.png'),
                            semantic_mask=semantic_masks.get(camera))
                        guided = world[completed]
                        evidence['post_guided_boundary_completion'] = continuation
                    seeds.append(guided)
                    records.append(evidence)
                measured = np.concatenate(seeds)
                # The same interval bounds cross-view depth connectivity.
                # Membership still requires a seeded 3 mm component and
                # the pre-lift static-scene veto; bounds alone own nothing.
                lower = measured.min(0)-temporal['surface_residual_m']
                upper = measured.max(0)+temporal['surface_residual_m']
                member, evidence = complete_spatial_payload_component(scene, measured,
                    self.payload_reference['scene'], lower, upper)
                result = np.concatenate([result, scene[member]])
                records.append(evidence)
        self._instance_cache[anchor_id] = result
        self.instance_boundary_evidence[anchor_id] = records
        return result

    def grasp_geometry(self, entity):
        """Reuse r9 proposals, screening the entire actual smooth approach."""
        from robots.libero.v5_grasp_route import sample_unified_grasps

        points = self.scene.measurement_clouds.get(entity.id)
        if points is None or len(points) < 40:
            return None
        robot = measured_robot(self.p)
        # Fit normals/contact patches on the fused geometry estimate. Raw
        # per-camera pixels are retained by screen for instance membership
        # and obstacle checks, not substituted for the fused fit surface.
        # Existing measured contacts may all have blocked approach/closure
        # routes. Only then expand the same sampler to lower side contours.
        for include_band_seeds in (False, True):
            _, records = sample_unified_grasps(points, np.empty((0, 3)), entity.name,
                robot['eef_xyz_m'], robot['eef_quat_xyzw'], self.geometry, None,
                robot['eef_xyz_m'][2], candidate_only=True, include_band_seeds=include_band_seeds)
            proposals = [row for row in records if not row['rejected']]
            if not proposals:
                self.candidate_diagnostics.append({'stage': 'grasp_route_search', 'anchor_id': entity.id,
                    'label': entity.name, 'selected': None, 'candidates': records})
                return self._surface_contact_plan(entity, points)
            # Do not build/subtract full-resolution clouds for surfaces whose
            # measured flanks already rule out every grasp (e.g. the table).
            screen = self._cloud_and_ik(entity.id, contact=True)
            from scipy.spatial import cKDTree
            obstacle_tree = cKDTree(screen.points) if len(screen.points) else None
            for row in proposals:
                clearance = min(float(obstacle_tree.query(row['xyz'])[0]), .2) if obstacle_tree else .2
                row['score'] += (clearance-row.get('clearance_m', clearance))/.2
                row['clearance_m'] = clearance
            current = Rotation.from_quat(robot['eef_quat_xyzw'])
            for row in records:
                if row['rejected']:
                    continue
                original = Rotation.from_quat(row['body_quat_xyzw'])
                best = min((original, original*Rotation.from_euler('z', math.pi)),
                           key=lambda q: (q*current.inv()).magnitude())
                for waypoint in row['route']:
                    if (Rotation.from_quat(waypoint['body_quat_xyzw'])*original.inv()).magnitude() < 1e-6:
                        waypoint['body_quat_xyzw'] = best.as_quat().tolist()
                row['body_quat_xyzw'] = best.as_quat().tolist()
                row['wrist_change_rad'] = float((best*current.inv()).magnitude())
                row['score'] -= .25*row['wrist_change_rad']/math.pi
            records.sort(key=lambda r: (bool(r['rejected']), -r.get('score', -1), r['id']))
            chosen = None
            for row in records:
                if row['rejected']:
                    continue
                if chosen is not None:
                    row['route_status'] = 'not_screened_lower_rank'
                    continue
                route = [{'xyz_m': w['xyz'], 'quat_xyzw': w['body_quat_xyzw']} for w in row['route']]
                _, _, _, evidence = SmoothMotion(self.p, screen, self.config).prepare(route)
                row['route_status'] = 'passed' if evidence['passed'] else 'rejected'
                row['route_screen'] = {k: evidence[k] for k in (
                    'reason', 'passed', 'path_min_clearance_m', 'collision', 'ik_reachable', 'at', 'counts',
                    'target_counts') if k in evidence}
                if not evidence['passed']:
                    row['rejected'].append(evidence['reason'])
                    continue
                # Closing sweeps all jaw openings at the measured contact pose;
                # only the selected object's finger contact is permitted.
                from robots.libero.v5_geometric_grasp import collision_counts
                site = Rotation.from_quat(row['body_quat_xyzw']).as_matrix()@Rotation.from_euler('z', -math.pi/2).as_matrix()
                for opening in np.linspace(.08, 0., 9):
                    external = collision_counts(screen.points, row['xyz'], site, self.geometry, opening, clearance_m=.004)
                    own = collision_counts(screen.target, row['xyz'], site, self.geometry, opening, clearance_m=.004)
                    if any(external.values()) or own.get('palm', 0):
                        row['rejected'].append('closure_sweep_collision')
                        row['route_status'] = 'rejected'
                        row['closure'] = {'opening_m': float(opening), 'scene': external, 'target': own}
                        break
                if not row['rejected']:
                    chosen = row
            self.candidate_diagnostics.append({'stage': 'grasp_route_search', 'anchor_id': entity.id,
                'label': entity.name, 'selected': chosen['id'] if chosen else None, 'candidates': records,
                'sampling_pass': 'route_fallback_bands' if include_band_seeds else 'primary'})
            if chosen is not None:
                break
        if chosen is None:
            return self._surface_contact_plan(entity, points)
        outward = np.asarray(chosen['approach_xyz'])-chosen['xyz']
        right, front = map(np.asarray, self.scene.view_axes)
        directions = {'above': np.array([0., 0., 1.]), 'front': front, 'left': -right, 'right': right}
        approach = max(directions, key=lambda key: np.dot(outward, directions[key]))
        return {'xyz_m': chosen['xyz'], 'quat_xyzw': chosen['body_quat_xyzw'],
            'width_m': chosen['width_m'], 'quality': chosen['measurement_confidence'],
            'approach_xyz_m': chosen['approach_xyz'], 'preferred_approach': approach,
            'approach_route': [{'xyz_m': w['xyz'], 'quat_xyzw': w['body_quat_xyzw']}
                               for w in chosen['route'][:-1]],
            'grasp_candidate_id': chosen['id']}

    def _surface_contact_plan(self, entity, points):
        """Offer bounded contact on a measured thin surface, without claiming a grasp."""
        lower, upper = np.quantile(points, [.02, .98], axis=0)
        extent = upper-lower
        robot = measured_robot(self.p)
        centre = np.median(points, axis=0)
        horizontal = extent[2] <= .02 and min(extent[:2]) >= max(.04, 4*extent[2])
        if horizontal:
            normal = np.array([0., 0., 1.])
            outward = np.asarray(robot['eef_xyz_m'][:2])-centre[:2]
            norm = np.linalg.norm(outward)
            outward = np.asarray(self.scene.view_axes[1])[:2] if norm < .001 else outward/norm
            projection = (points[:, :2]-centre[:2])@outward
            edge = points[projection >= np.quantile(projection, .97)]
            contact = np.median(edge, axis=0)
        else:
            _, axes = np.linalg.eigh(np.cov(np.asarray(points).T))
            dimensions = np.diff(np.quantile((points-centre)@axes, [.02, .98], axis=0), axis=0)[0]
            if dimensions[0] > .02 or min(dimensions[1:]) < max(.04, 4*dimensions[0]):
                return None
            normal = axes[:, 0]
            # A parent's visible centroid can lie on either side of a moving
            # panel. Approach the observed face from the measured hand side;
            # the unchanged full-route screen still decides reachability.
            outward = np.asarray(robot['eef_xyz_m'])-centre
            if np.dot(normal, outward) < 0:
                normal = -normal
            # The selected contact is an actual measured surface point.
            contact = points[np.argmin(np.linalg.norm(points-centre, axis=1))]
        right = np.asarray(self.scene.view_axes[0])
        right = right-normal*np.dot(right, normal)
        if np.linalg.norm(right) < .1:
            right = np.cross(normal, [0., 0., 1.])
        right /= np.linalg.norm(right)
        pads = [b for b in self.geometry['boxes'] if b['name'].endswith('_pad')]
        tip = np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in pads], axis=0)
        # A thin surface needs tip contact, not pad-centre alignment: the
        # latter puts the longer finger body through its supporting plane.
        tip[2] = max(b['upper'][2] for b in self.geometry['boxes'] if 'finger' in b['name'])
        current = Rotation.from_quat(robot['eef_quat_xyzw'])
        contacts = [contact]
        if horizontal:
            # A neighbour can block every wrist orientation at the nearest
            # rim. Sample the same measured perimeter for any thin surface;
            # no object class or task target chooses these contact patches.
            for angle in range(45, 360, 45):
                direction = Rotation.from_euler('z', angle, degrees=True).apply(np.r_[outward, 0.])[:2]
                projection = (points[:, :2]-centre[:2])@direction
                edge = points[projection >= np.quantile(projection, .97)]
                patch = np.median(edge, axis=0)
                if all(np.linalg.norm(patch-other) >= .01 for other in contacts):
                    contacts.append(patch)
        choices = []
        for patch_index, patch in enumerate(contacts):
            normals = [normal]
            if horizontal:
                # A thin rim can be inclined while its overall support is
                # horizontal. Align tip contact to that measured patch;
                # a fixed downward tip only skims its upper surface.
                local = points[np.linalg.norm(points-patch, axis=1) <= .015]
                if len(local) >= 8:
                    values, axes = np.linalg.eigh(np.cov(local.T))
                    fitted = axes[:, 0]
                    if fitted@normal < 0:
                        fitted = -fitted
                    if (values[1] > 1e-8 and values[0] <= .2*values[1]
                            and fitted@normal >= .5 and fitted@normal < .999):
                        normals.insert(0, fitted)
            approaches = [(value, 'measured_surface_normal', value) for value in normals]
            if horizontal:
                # The measured upper contour is also a contact point. A
                # fixed oblique approach can keep the palm above its support
                # while placing the fingertip against that contour. This is
                # an approach direction, not an inferred unseen side plane.
                radial = np.r_[patch[:2]-centre[:2], 0.]
                if np.linalg.norm(radial) >= .02:
                    radial /= np.linalg.norm(radial)
                    for angle in (30., 45., 60.):
                        direction = radial*math.cos(math.radians(angle))
                        direction[2] = math.sin(math.radians(angle))
                        approaches.append((direction, 'measured_contour_fixed_incline', normals[0]))
            for patch_normal, approach_basis, measured_normal in approaches:
                tangent = right-patch_normal*(right@patch_normal)
                if np.linalg.norm(tangent) < .1:
                    tangent = np.cross(patch_normal, [0., 0., 1.])
                tangent /= np.linalg.norm(tangent)
                for yaw in range(0, 360, 45):
                    closing = Rotation.from_rotvec(patch_normal*math.radians(yaw)).apply(tangent)
                    site = side_site_rotation(closing, -patch_normal)
                    orientation = Rotation.from_matrix(site@Rotation.from_euler('z', math.pi/2).as_matrix())
                    # Parallel fingers admit both wrist orientations. The shorter
                    # rotation can reach a joint limit while its symmetric pose has
                    # a continuous IK route, so screen both instead of pruning one.
                    xyz = patch-site@tip
                    entry = xyz+patch_normal*.12
                    height = max(robot['eef_xyz_m'][2], entry[2])+.08
                    over = [{'xyz_m': [*robot['eef_xyz_m'][:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': [*entry[:2], height], 'quat_xyzw': orientation.as_quat().tolist()},
                        {'xyz_m': entry.tolist(), 'quat_xyzw': orientation.as_quat().tolist()},
                        {'xyz_m': xyz.tolist(), 'quat_xyzw': orientation.as_quat().tolist()}]
                    routes = [('over', over)] if horizontal else [('direct', over[-2:]), ('over', over)]
                    for path, route in routes:
                        choices.append({'patch_index': patch_index, 'contact_xyz_m': patch.tolist(),
                            'normal_xyz': patch_normal.tolist(),
                            'measured_normal_xyz': measured_normal.tolist(), 'approach_basis': approach_basis,
                            'local_normal': bool(approach_basis == 'measured_surface_normal'
                                and not np.array_equal(patch_normal, normal)),
                            'yaw_deg': yaw, 'path': path, 'xyz_m': xyz.tolist(),
                            'quat_xyzw': orientation.as_quat().tolist(), 'approach_xyz_m': entry.tolist(), 'route': route,
                            'wrist_change_rad': float((orientation*current.inv()).magnitude()), 'screen': None})
        choices.sort(key=lambda item: (abs(item['normal_xyz'][2]) if horizontal else 0.,
            not item['local_normal'], item['patch_index'], item['wrist_change_rad'], item['yaw_deg']))
        screen = self._cloud_and_ik(entity.id, contact=True)
        def screened(option):
            if option.get('screen') is not None:
                return option['screen']['passed']
            if option.get('closure'):
                return False
            from robots.libero.v5_geometric_grasp import collision_counts
            site = Rotation.from_quat(option['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -math.pi/2).as_matrix()
            for opening in np.linspace(.08, 0., 9):
                external = collision_counts(screen.points, option['xyz_m'], site, self.geometry, opening, clearance_m=.004)
                own = collision_counts(screen.target, option['xyz_m'], site, self.geometry, opening, clearance_m=.004)
                if any(external.values()) or own.get('palm', 0):
                    option['closure'] = {'opening_m': float(opening), 'scene': external, 'target': own}
                    break
            if option.get('closure'):
                return False
            _, _, _, evidence = SmoothMotion(self.p, screen, self.config).prepare(option['route'])
            option['screen'] = {k: evidence[k] for k in ('passed', 'reason', 'collision', 'ik_reachable', 'path_min_clearance_m')}
            if not horizontal and evidence['passed']:
                margins = [solve['joint_margin_min_rad'] for check in evidence.get('ik_checks', [])
                    for solve in check['solves'] if solve['solution_found']]
                option['screen']['route_joint_margin_rad'] = min(margins) if margins else None
                option['screen']['contact_joint_margin_rad'] = margins[-1] if margins else None
            return evidence['passed']
        if horizontal:
            selected = next((option for option in choices if screened(option)), None)
        else:
            # Reaching a panel with a wrist at its joint stop leaves no room
            # to follow the moving face. Compare the same screened contacts
            # by terminal joint margin, as for measured handle approaches.
            feasible = [option for option in choices if screened(option)]
            selected = max(feasible, key=lambda option: (
                option['screen']['contact_joint_margin_rad'] or 0.,
                option['screen']['route_joint_margin_rad'] or 0.)) if feasible else None
            if selected is None:
                from robots.libero.bounded_joint_routes import contact_guides

                for option in contact_guides(screen, robot, choices):
                    choices.append(option)
                    if screened(option):
                        selected = option
                        break
        right_axis, front = map(np.asarray, self.scene.view_axes)
        directions = {'above': np.array([0., 0., 1.]), 'front': front,
                      'left': -right_axis, 'right': right_axis}
        directional = {}
        if horizontal and selected is not None:
            directional['above'] = selected
            for name in ('front', 'left', 'right'):
                direction = directions[name]
                ranked = sorted(choices, key=lambda option:
                    -float((np.asarray(option['contact_xyz_m'])-centre)@direction))
                option = next((option for option in ranked
                    if (np.asarray(option['contact_xyz_m'])-centre)@direction > 0.
                    and screened(option)), None)
                if option is not None:
                    directional[name] = option
        self.candidate_diagnostics.append({'stage': 'measured_surface_contact', 'anchor_id': entity.id,
            'source': 'fused_rgbd_shape_and_static_finger_tip_geometry',
            'contact_xyz_m': selected['contact_xyz_m'] if selected else None,
            'contact_patches_xyz_m': [patch.tolist() for patch in contacts], 'measured_extent_m': extent.tolist(),
            'surface_normal_xyz': selected['measured_normal_xyz'] if selected else normal.tolist(),
            'contact_approach_xyz': selected['normal_xyz'] if selected else None,
            'approach_basis': selected['approach_basis'] if selected else None,
            'object_plane_normal_xyz': normal.tolist(),
            'grasp_verified': False, 'candidates': choices,
            'directional_contact_points': {name: option['contact_xyz_m']
                for name, option in directional.items()},
            'selected_yaw_deg': selected['yaw_deg'] if selected else None})
        if selected is None:
            return None
        pixels = self._instance_pixels(entity.id).tolist()
        def contact_plan(option, approach=None):
            normal = np.asarray(option['normal_xyz'])
            return {k: option[k] for k in ('xyz_m', 'quat_xyzw', 'approach_xyz_m')} | {
                'approach_route': option.get('approach_route', option['route'][:-1]),
                **({'contact_route': option['contact_route']} if 'contact_route' in option else {}),
                'preferred_approach': approach or max(directions, key=lambda key: np.dot(normal, directions[key])),
                'preferred_path': option['path'],
                'width_m': None, 'contact_kind': 'surface',
                'contact_point_xyz_m': option['contact_xyz_m'],
                'contact_approach_xyz': normal.tolist(), 'approach_basis': option['approach_basis'],
                'surface_measurement': {'xyz_world': pixels,
                    'source_step': entity.source_step, 'normal_xyz': option['measured_normal_xyz']}}
        plan = contact_plan(selected)
        if directional:
            plan['surface_contact_options'] = {name: contact_plan(option, name)
                for name, option in directional.items()}
        return plan

    def _refresh_contact_normal(self, entity, plan):
        """Refit a contacted panel's normal from its current measured surface.

        Keep the original contact pixels for collision association. Only a
        fresh, visibly planar patch may update the movement direction; a
        thin handle or an occluded/stale capture supplies no panel normal.
        """
        surface = plan.get('surface_measurement')
        if (not surface or not entity.visible
                or entity.source_step != self.ex.toolkit._state.latest_step):
            return
        points = np.asarray(self.scene.measurement_clouds.get(entity.id, []), dtype=float).reshape(-1, 3)
        points = points[np.isfinite(points).all(axis=1)]
        if len(points) < 40:
            return
        centre = np.median(points, axis=0)
        _, axes = np.linalg.eigh(np.cov(points.T))
        dimensions = np.diff(np.quantile((points-centre)@axes, [.02, .98], axis=0), axis=0)[0]
        # Two broad tangents must support the normal. Unlike selecting a
        # fingertip contact, orienting the measured face does not require
        # its parallel recessed surfaces to fit within a 2 cm slab.
        if min(dimensions[1:]) < max(.04, 4*dimensions[0]):
            return
        normal = axes[:, 0]
        if np.dot(normal, surface['normal_xyz']) < 0:
            normal = -normal
        surface['normal_xyz'] = normal.tolist()
        surface['normal_source_step'] = entity.source_step

    def _fixture_closure_aperture(self, points, contact, orientation):
        """Measure first contact in each finger's finite sliding convex hull.

        The projection of an entire oblique bar includes ends outside the
        fingers. Only its observed surface inside the real closure sweep
        contributes to the predicted aperture. Missing bilateral coverage
        returns no estimate; it never asserts an empty or successful grasp.
        """
        rotation = (orientation*Rotation.from_euler('z', -math.pi/2)).as_matrix()
        local = (np.asarray(points)-contact)@rotation
        fingers = {'leftfinger': [], 'rightfinger': []}
        for box in self.geometry['boxes']:
            side = next((name for name in fingers if box['name'].startswith(name)), None)
            if side is None or not box.get('convex_halfspaces') or not box.get('slide_per_half_opening'):
                continue
            planes = np.asarray(box['convex_halfspaces'])
            c = planes[:, :3]@box['slide_per_half_opening']
            b = local@planes[:, :3].T+planes[:, 3]
            positive, negative, fixed = c > 1e-9, c < -1e-9, abs(c) <= 1e-9
            lower = np.maximum(0., np.max(b[:, positive]/c[positive], axis=1)) if positive.any() else np.zeros(len(local))
            upper = np.minimum(self.geometry['max_opening_m']/2,
                np.min(b[:, negative]/c[negative], axis=1)) if negative.any() else np.full(
                    len(local), self.geometry['max_opening_m']/2)
            eligible = (lower <= upper) & (b[:, fixed] <= 1e-9).all(axis=1)
            if eligible.any():
                fingers[side].append(float(upper[eligible].max()))
        if not all(fingers.values()):
            return None
        contacts = {side: max(values) for side, values in fingers.items()}
        return {'source': 'public_handle_pixels_and_static_finger_closure_hulls',
            'width_m': sum(contacts.values()), 'finger_half_apertures_m': contacts}

    def _screen_fixture_approaches(self, entity, plan):
        """Select a measured handle entry with a clear complete contact route.

        A fixed stand-off can put the palm in another fixture. Search the
        same geometric alternatives for every handle, retaining the existing
        collision margin, contact exceptions and numerical IK checks.
        """
        robot = measured_robot(self.p)
        contact = np.asarray(plan['xyz_m'])
        normal = np.asarray(plan['approach_xyz_m'])-contact
        normal /= np.linalg.norm(normal)
        current = Rotation.from_quat(robot['eef_quat_xyzw'])
        original = Rotation.from_quat(plan['quat_xyzw'])
        orientations = []
        handle_points = self._handle_pixels(plan.get('handle_measurement'))
        for roll in (0, -45, 45):
            oblique = Rotation.from_rotvec(normal*math.radians(roll))*original
            for orientation in sorted((oblique, oblique*Rotation.from_euler('z', math.pi)),
                    key=lambda q: (q*current.inv()).magnitude()):
                width = plan.get('width_m')
                aperture = None
                if len(handle_points) >= 10:
                    closing = (orientation*Rotation.from_euler('z', -math.pi/2)).as_matrix()[:, 0]
                    extent = np.quantile(handle_points@closing, [.02, .98])
                    width = float(extent[1]-extent[0])
                    aperture = self._fixture_closure_aperture(handle_points, contact, orientation)
                    if aperture is not None:
                        width = aperture['width_m']
                orientations.append((orientation, roll, width, aperture))
        choices = []
        for orientation, roll, width, aperture in orientations:
            quat = orientation.as_quat().tolist()
            for distance in (.12, .08, .04):
                entry = contact+normal*distance
                height = max(robot['eef_xyz_m'][2], entry[2])+.08
                high_start = [*robot['eef_xyz_m'][:2], height]
                high_entry = [*entry[:2], height]
                for rotate_at in ('entry', 'clearance', 'entry_direct', 'current_direct'):
                    route = [
                        {'xyz_m': high_start, 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': high_entry, 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': entry.tolist(), 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': entry.tolist(), 'quat_xyzw': quat}]
                    if rotate_at == 'clearance':
                        route = [route[0], {'xyz_m': high_start, 'quat_xyzw': quat},
                            {'xyz_m': high_entry, 'quat_xyzw': quat}, route[-1]]
                    if rotate_at == 'entry_direct':
                        route = [route[2], route[3]]
                    elif rotate_at == 'current_direct':
                        route = [{'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': quat}, route[3]]
                    route.append({'xyz_m': contact.tolist(), 'quat_xyzw': quat})
                    choices.append({'stand_off_m': distance, 'rotate_at': rotate_at,
                        'handle_roll_deg': roll, 'width_m': width, 'closure_aperture': aperture,
                        'route': route, 'screen': None})
        screen = self._cloud_and_ik(entity.id, contact=True)
        selected = None
        accepted_orientations = set()
        for index, option in enumerate(choices):
            # Compare the two parallel-finger-equivalent wrist poses before
            # choosing. A numerically reachable pose at a joint limit can
            # stall the OSC descent while its symmetric pose remains usable.
            if selected is not None and option['handle_roll_deg'] != choices[selected]['handle_roll_deg']:
                break
            orientation_key = tuple(option['route'][-1]['quat_xyzw'])
            if orientation_key in accepted_orientations:
                continue
            if any(np.linalg.norm(contact-np.asarray(failed['xyz_m'])) < .01
                    and (Rotation.from_quat(option['route'][-1]['quat_xyzw'])*
                         Rotation.from_quat(failed['quat_xyzw']).inv()).magnitude() < .05
                    for failed in self.failed_contact_poses.get(entity.id, [])):
                option['screen'] = {'passed': False, 'reason': 'measured_joint_limit_during_prior_descent',
                    'collision': None, 'ik_reachable': None, 'path_min_clearance_m': None}
                continue
            if option['width_m'] is not None and option['width_m'] > self.geometry['max_opening_m']:
                option['screen'] = {'passed': False, 'reason': 'measured_handle_width_exceeds_opening',
                    'collision': None, 'ik_reachable': None, 'path_min_clearance_m': None}
                continue
            _, _, _, evidence = SmoothMotion(self.p, screen, self.config).prepare(option['route'])
            option['screen'] = {key: evidence[key] for key in (
                'passed', 'reason', 'collision', 'ik_reachable', 'path_min_clearance_m',
                'at', 'counts', 'target_counts', 'public_scene_collision_points',
                'public_target_collision_points') if key in evidence}
            if evidence['passed']:
                margins = [solve['joint_margin_min_rad'] for check in evidence.get('ik_checks', [])
                    for solve in check['solves'] if solve['solution_found']]
                option['screen']['route_joint_margin_rad'] = min(margins) if margins else None
                option['screen']['contact_joint_margin_rad'] = margins[-1] if margins else None
                accepted_orientations.add(orientation_key)
                if selected is None or ((option['screen']['contact_joint_margin_rad'] or 0.,
                        option['screen']['route_joint_margin_rad'] or 0.)
                        > (choices[selected]['screen']['contact_joint_margin_rad'] or 0.,
                           choices[selected]['screen']['route_joint_margin_rad'] or 0.)):
                    selected = index
        self.candidate_diagnostics.append({'stage': 'fixture_route_search',
            'anchor_id': entity.id, 'source': 'measured_handle_and_static_gripper_geometry',
            'selected': selected, 'candidates': choices})
        if selected is None:
            return None
        route = choices[selected]['route']
        return {**plan, 'quat_xyzw': route[-1]['quat_xyzw'],
            'width_m': choices[selected]['width_m'],
            'closure_aperture': choices[selected]['closure_aperture'],
            'preferred_path': 'direct' if choices[selected]['rotate_at'].endswith('_direct') else 'over',
            'approach_xyz_m': route[-2]['xyz_m'], 'approach_route': route[:-1]}

    def _transport_alignment(self, robot):
        """Align the held hand to an observed support plane, retaining yaw."""
        surface = getattr(self.scene, 'work_surface_measurement', None)
        if surface is None or 'normal_xyz' not in surface:
            state = getattr(getattr(self.ex, 'toolkit', None), '_state', None)
            if state is None:
                return None
            from robots.libero.v5_perception_geometry import measured_work_surface

            anchors = [e for e in self.scene.entities.values()
                if e.id != self.held and e.visible and not e.part_of]
            for camera in ('agentview', 'wrist'):
                world = np.asarray(state.load(camera+'_world_high.npz'))
                surface = measured_work_surface(world, anchors)
                if surface is not None:
                    surface.update(camera=camera, source_step=state.latest_step, source='perception')
                    self.scene.work_surface_measurement = surface
                    break
            if surface is None:
                return None
        normal = np.asarray(surface['normal_xyz'])
        if normal@(np.asarray(robot['eef_xyz_m'])-surface['centroid_xyz']) < 0:
            normal = -normal
        current = Rotation.from_quat(robot['eef_quat_xyzw'])
        site = current.as_matrix()@Rotation.from_euler('z', -math.pi/2).as_matrix()
        closing = site[:, 0]-normal*(site[:, 0]@normal)
        if np.linalg.norm(closing) < 1e-6:
            closing = site[:, 1]-normal*(site[:, 1]@normal)
        desired = Rotation.from_matrix(side_site_rotation(closing, -normal)
            @Rotation.from_euler('z', math.pi/2).as_matrix())
        if (desired*current.inv()).magnitude() < .05:
            return None
        self.candidate_diagnostics.append({'stage': 'held_support_alignment',
            'anchor_id': self.held, 'measured_support': surface,
            'quat_xyzw': desired.as_quat().tolist()})
        return [{'xyz_m': list(robot['eef_xyz_m']), 'quat_xyzw': desired.as_quat().tolist()}]

    def _route(self, skill, parameters, *, robot=None):
        robot = robot or measured_robot(self.p)
        start = np.array(robot["eef_xyz_m"])
        quat = robot["eef_quat_xyzw"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        if skill == 'align' and self.held is not None and key == self.held:
            return self._transport_alignment(robot)
        entity = self.scene.entities.get(key)
        if self.held is not None and key != self.held and key in self.target_cache:
            entity = self.target_cache[key]
        elif entity is None or not entity.visible:
            entity = self.target_cache.get(key)
        point = start.copy()
        if skill in {"move_to", "align", "descend"}:
            contact = self.plans.get(key)
            approach = parameters.get("approach", "above")
            if skill == 'move_to' and contact is not None and 'surface_contact_options' in contact:
                contact = contact['surface_contact_options'].get(approach)
                if contact is None:
                    return None
            right, front = map(np.asarray, self.scene.view_axes)
            direction = {"above": np.array([0., 0., 1.]), "front": front,
                         "left": -right, "right": right}[approach]
            if contact is None:
                if skill != 'move_to' or entity is None or not entity.visible:
                    return None
                # A failed opposing-contact fit does not erase a measured
                # anchor. Offer a noncontact observation approach outside
                # its measured bounds, retaining the current wrist pose.
                # The normal full-hand sweep and IK screen still apply.
                lower, upper = np.asarray(entity.lower), np.asarray(entity.upper)
                goal = (lower+upper)/2
                point = goal+direction*(float(np.abs(direction)@(upper-lower))/2+.12)
            else:
                goal = np.array(contact["xyz_m"])
                if skill == "align":
                    return [{"xyz_m": start.tolist(), "quat_xyzw": contact["quat_xyzw"]}]
                if skill == "descend":
                    return copy.deepcopy(contact.get('contact_route',
                        [{"xyz_m": goal.tolist(), "quat_xyzw": contact["quat_xyzw"]}]))
                preferred = approach == contact.get('preferred_approach')
                if preferred and parameters['path'] == contact.get('preferred_path', 'over'):
                    return copy.deepcopy(contact['approach_route'])
                point = np.asarray(contact['approach_xyz_m']) if preferred else goal+direction*.12
                quat = contact["quat_xyzw"]
            path = parameters["path"]
            if path == "over":
                height = max(start[2], point[2])+ .08
                return [{"xyz_m": [*start[:2], height], "quat_xyzw": robot["eef_quat_xyzw"]},
                        {"xyz_m": [*point[:2], height], "quat_xyzw": quat},
                        {"xyz_m": point.tolist(), "quat_xyzw": quat}]
            if path == "around":
                middle = (start+point)/2+right*.12
                middle[2] = max(start[2], point[2])
                return [{"xyz_m": middle.tolist(), "quat_xyzw": robot["eef_quat_xyzw"]},
                        {"xyz_m": point.tolist(), "quat_xyzw": quat}]
        elif skill == "lift":
            point[2] += .10
        elif skill in {"carry_to", "lower"}:
            if entity is None or self.held is None:
                return None
            held = self.scene.entities.get(self.held)
            if held is None:
                return None
            # A visible-surface median can sit on a container wall or the
            # near side of a held object. Reuse v5 place's measured-bound
            # midpoint for BOTH sides of the transport offset. No unseen
            # dimensions, task predicate or simulator pose is completed.
            held_centre = (np.asarray(held.lower)+held.upper)/2
            target_centre = (np.asarray(entity.lower)+entity.upper)/2
            offset = start-held_centre
            point = target_centre+offset
            if skill == "carry_to":
                # Carry clears the destination before lateral transport;
                # lowering belongs to the separately selected lower skill.
                point[2] = max(start[2], entity.upper[2]+max(.12, start[2]-held.lower[2]))
                if point[2] > start[2]:
                    return [{"xyz_m": [*start[:2], point[2]], "quat_xyzw": quat},
                            {"xyz_m": point.tolist(), "quat_xyzw": quat}]
            else:
                point[2] = entity.upper[2]+(start[2]-held.lower[2])+.012
        elif skill == "nudge":
            point["xyz".index(parameters["axis"])] += parameters["distance_m"]
        elif skill == "rotate_wrist":
            quat = (Rotation.from_quat(quat)*Rotation.from_euler("z", parameters["angle_deg"], degrees=True)).as_quat().tolist()
        return [{"xyz_m": point.tolist(), "quat_xyzw": quat}]

    def _candidate(self, skill, parameters, *, screen_options=True):
        cid = hashlib.sha256(identity({"skill": skill, "parameters": parameters}).encode()).hexdigest()[:16]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        if key is None and skill in {'nudge', 'rotate_wrist'}:
            key = self.active
        entity = self.scene.entities.get(key)
        if key is not None and not self._has_anchor(entity):
            return None
        if key in self.target_cache and (
                (self.held is not None and key != self.held) or not entity.visible):
            entity = self.target_cache[key]
        consequence = {"path_min_clearance_m": None, "collision": None, "ik_reachable": None,
                       "expected_width_m": self.plans.get(key, {}).get("width_m"),
                       "expected_gripper_opening_m": None, "expected_steps": 0,
                       "screen_scope": "nonmotion", "evidence_ids": [e['measurement_id']
                           for e in self._anchor_evidence(entity)] if entity else []}
        if skill in MOTION_SKILLS:
            route = self._route(skill, parameters)
            if route is None:
                if skill not in {'carry_to', 'lower'}:
                    return None
                # Available after a measured-anchor grasp within this chunk.
                # No initial collision/IK result is claimed for that prefix.
                consequence['screen_scope'] = 'conditional_on_prefix'
                return {'id': cid, 'skill': skill, 'parameters': parameters,
                    'consequences': consequence, 'history': None,
                    'recent_failures': 0, 'last_failure': None,
                    'expected_receipt': expected_receipt(self, skill, parameters)}
            contact = skill in {"descend", "lower", "nudge"} or (skill in {"lift", "rotate_wrist"} and self.active is not None)
            motion = SmoothMotion(self.p, self._cloud_and_ik(key, contact=contact), self.config)
            trajectory, _, _, evidence = motion.prepare(route)
            if not evidence['passed']:
                self.candidate_diagnostics.append({'candidate_id': cid, 'skill': skill, 'parameters': parameters,
                    **{field: evidence[field] for field in ('reason', 'at', 'counts', 'target_counts',
                        'path_min_clearance_m', 'public_nearby_points', 'payload_point', 'obstacle_point',
                        'public_scene_collision_points', 'public_target_collision_points') if field in evidence}})
            consequence.update({field: evidence[field] for field in ("path_min_clearance_m", "collision", "ik_reachable")})
            consequence["screen_scope"] = "contact_selected_surface" if contact else "hand_mesh_observed_space"
            consequence["expected_steps"] = math.ceil(trajectory.duration*self.config.hz)
        elif skill in {"release", "set_gripper"}:
            consequence.update(expected_steps=15, expected_gripper_opening_m=(.08 if skill == "release" or parameters.get("mode") == "open" else 0.))
        history = None
        if skill == "call_vla":
            estimate = self.history.estimate(parameters["mode"], entity.name)
            history = {field: estimate[field] for field in ("success_rate", "n", "expected_steps")}
            history["source_manifest_sha256"] = self.history.manifest_sha256
            consequence["expected_steps"] = estimate["expected_steps"] or 240
            consequence["screen_scope"] = "unmeasured"
        return {"id": cid, "skill": skill, "parameters": parameters, "consequences": consequence,
                "history": history, "recent_failures": 0, "last_failure": None,
                "expected_receipt": expected_receipt(self, skill, parameters,
                    route if skill in MOTION_SKILLS else None)}

    def _refresh_held_measurement(self):
        """Use the cleaned current payload for carry and lower anchor bounds."""
        if self.held is None or self.payload_reference is None:
            return
        entity = self.scene.entities.get(self.held)
        if entity is None:
            return
        screen = self._cloud_and_ik(self.held, contact=True)
        if len(screen.payload) < 40:
            return
        robot = measured_robot(self.p)
        points = screen.payload@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m']
        lower, upper = np.quantile(points, [.02, .98], axis=0)
        self.scene.entities[self.held] = replace(entity, xyz=tuple(np.median(points, axis=0)),
            lower=tuple(lower), upper=tuple(upper), visible=True,
            source_step=self.ex.toolkit._state.latest_step, geometry='current_rgbd_clean_payload_surface')
        self.scene.measurement_clouds[self.held] = points

    @staticmethod
    def _held_motion_evidence(prior, current, before, after):
        """Detect a fresh visible object outside its transported measured bounds."""
        if (prior is None or current is None or not prior.visible or not current.visible
                or current.source_step <= prior.source_step):
            return None
        corners = np.array([[x, y, z] for x in (prior.lower[0], prior.upper[0])
            for y in (prior.lower[1], prior.upper[1]) for z in (prior.lower[2], prior.upper[2])])
        local = Rotation.from_quat(before['eef_quat_xyzw']).inv().apply(corners-before['eef_xyz_m'])
        predicted = Rotation.from_quat(after['eef_quat_xyzw']).apply(local)+after['eef_xyz_m']
        lower, upper = predicted.min(axis=0), predicted.max(axis=0)
        gap = np.maximum(np.maximum(lower-current.upper, np.asarray(current.lower)-upper), 0.)
        distance = float(np.linalg.norm(gap))
        return {'source': 'paired_public_rgbd_bounds_and_proprioception',
            'before_capture_step': prior.source_step, 'after_capture_step': current.source_step,
            'predicted_lower_m': lower.tolist(), 'predicted_upper_m': upper.tolist(),
            'measured_lower_m': list(current.lower), 'measured_upper_m': list(current.upper),
            'extent_gap_m': distance, 'coupling_tolerance_m': .015,
            'lost': distance > .015}

    def _recheck_transport_hold(self, before, entities_before):
        """Clear a dropped attachment using public aperture or fresh RGB-D."""
        prior_held = before.get('held_anchor_id')
        if prior_held is None or self.held != prior_held:
            return None, None
        holding = self._held_motion_evidence(entities_before.get(prior_held),
            self.scene.entities.get(prior_held), before, self.robot())
        empty = self._empty_held_gripper(measured_robot(self.p))
        if (not empty and (holding is None or not holding['lost'])) or self.p.env.terminated:
            return holding, None
        if empty:
            holding = {'bounds_co_motion': holding, 'lost': True,
                'source': 'public_empty_gripper_during_transport',
                'opening_m': measured_robot(self.p)['gripper_opening_m']}
        self.held = self.active = self.ex.held = None
        self.grasp_reference = self.payload_reference = self.withdrawal_contact = None
        self.committed_grasps.pop(prior_held, None)
        self._screen_cache.clear()
        self._instance_cache.clear()
        return holding, prior_held

    def _empty_held_gripper(self, robot):
        """Interrupt held-object motion when the measured jaws close empty."""
        if self.held is None:
            return False
        _, evidence = self.holding_aperture(robot['gripper_opening_m'])
        lower = evidence.get('empty_closed_upper_m', .005)
        return robot['gripper_opening_m'] <= lower

    def request(self, *, k: int = 4, screen_options: bool = True):
        if k not in {1, 4}:
            raise ValueError("supported diagnostic K values are 1 and 4")
        self._refresh_held_measurement()
        self.plans.clear()
        self.candidate_diagnostics = []
        entities = [e for e in self.scene.entities.values() if self._has_anchor(e)]
        for entity in entities:
            if self.held is not None:
                # A held object exposes only carry/lower candidates. Keep
                # its public geometry for payload checks, without searching
                # unused new contact patches on every request.
                continue
            committed = self.committed_grasps.get(entity.id)
            fixture = bool(fixture_actions(entity.name))
            if committed is not None and fixture and self.active == entity.id and measured_robot(self.p)['gripper_opening_m'] < .075:
                # Contact can occlude the handle. Preserve the measured
                # contact identity for bounded nudges instead of planning a
                # second approach from inside the fixture. Current handle
                # pixels, when available, still update collision membership.
                plan = copy.deepcopy(committed['plan'])
                surface = plan.get('surface_measurement')
                if surface is not None:
                    surface.update(copy.deepcopy(committed.get('current_surface_normal', {})))
                self._refresh_contact_normal(entity, plan)
                if surface is not None and 'normal_source_step' in surface:
                    committed['current_surface_normal'] = {
                        field: copy.deepcopy(surface[field]) for field in ('normal_xyz', 'normal_source_step')}
                handle = self.scene.measure_fixture_handle_pose(entity, self.ex.instruction) if entity.visible else {}
                if handle.get('pose'):
                    plan['handle_measurement'] = handle
                self.plans[entity.id] = plan
                self.candidate_diagnostics.append({'stage': 'fixture_contact_plan',
                    'anchor_id': entity.id, 'label': entity.name, 'contact_committed': True,
                    'current_handle_measured': bool(handle.get('pose')), 'plan': copy.deepcopy(plan)})
                continue
            if committed is not None and (not fixture or measured_robot(self.p)['gripper_opening_m'] >= .075):
                # Keep one measured contact patch through approach/alignment.
                # A newly visible surface must not make a stationary object's
                # chosen rim point jump between successive bounded actions.
                if self.active == entity.id or np.linalg.norm(np.asarray(entity.xyz)-committed['anchor_xyz']) <= .01:
                    self.plans[entity.id] = copy.deepcopy(committed['plan'])
                    if fixture:
                        self.candidate_diagnostics.append({'stage': 'fixture_contact_plan',
                            'anchor_id': entity.id, 'label': entity.name,
                            'contact_committed': True, 'plan': copy.deepcopy(self.plans[entity.id])})
                    continue
                self.committed_grasps.pop(entity.id)
            if not entity.visible:
                continue  # Only an existing contact can reuse its cached fit.
            if fixture_actions(entity.name):
                handle = self.scene.measure_fixture_handle_pose(entity, self.ex.instruction)
                self.candidate_diagnostics.append({'stage': 'fixture_contact_measurement',
                    'anchor_id': entity.id, 'label': entity.name, 'measurement': handle})
                if not handle.get('pose'):
                    points = self.scene.measurement_clouds.get(entity.id)
                    if points is not None and len(points) >= 40:
                        contact = self._surface_contact_plan(entity, points)
                        if contact is not None:
                            self.plans[entity.id] = contact
                if handle.get("pose"):
                    pose = handle["pose"]
                    normal = np.array(pose.get("approach_normal_xyz", [*pose.get("approach_normal_xy", [0, -1]), 0.]))
                    closing = np.cross(normal, [0., 0., 1.])
                    if np.linalg.norm(closing) < .01:
                        closing = np.array([1., 0., 0.])
                    handle_points = self._handle_pixels(handle)
                    width = None
                    if len(handle_points) >= 10:
                        spread, axes = np.linalg.eigh(np.cov(handle_points.T))
                        # A bar is clamped across its short section, rather
                        # than trying to close along its measured long axis.
                        cross = np.cross(normal, axes[:, -1])
                        if spread[-1] > 2*spread[-2] and np.linalg.norm(cross) > .1:
                            closing = cross/np.linalg.norm(cross)
                            extent = np.quantile(handle_points@closing, [.02, .98])
                            width = float(extent[1]-extent[0])
                    site = side_site_rotation(closing, -normal)
                    pads = [b for b in self.geometry['boxes'] if b['name'].endswith('_pad')]
                    pad_centre = np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in pads], axis=0)
                    contact = np.asarray(pose['xyz'])-site@pad_centre
                    entry = contact+normal*.12
                    robot = measured_robot(self.p)
                    height = max(robot['eef_xyz_m'][2], entry[2])+.08
                    orientation = Rotation.from_matrix(site@Rotation.from_euler('z', math.pi/2).as_matrix())
                    current = Rotation.from_quat(robot['eef_quat_xyzw'])
                    # Swapping the parallel fingers preserves this measured
                    # contact, while avoiding an unnecessary half-turn into
                    # the wrist joint limit.
                    orientation = min((orientation, orientation*Rotation.from_euler('z', math.pi)),
                        key=lambda q: (q*current.inv()).magnitude())
                    quat = orientation.as_quat().tolist()
                    right, front = map(np.asarray, self.scene.view_axes)
                    directions = {'above': np.array([0., 0., 1.]), 'front': front, 'left': -right, 'right': right}
                    preferred = max(directions, key=lambda key: np.dot(normal, directions[key]))
                    self.plans[entity.id] = {'xyz_m': contact.tolist(), 'quat_xyzw': quat,
                        'width_m': width, 'handle_measurement': handle,
                        'approach_xyz_m': entry.tolist(), 'preferred_approach': preferred,
                        'approach_route': [
                            {'xyz_m': [*robot['eef_xyz_m'][:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
                            {'xyz_m': [*entry[:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
                            {'xyz_m': entry.tolist(), 'quat_xyzw': robot['eef_quat_xyzw']},
                            {'xyz_m': entry.tolist(), 'quat_xyzw': quat}]}
                    screened = self._screen_fixture_approaches(entity, self.plans[entity.id])
                    if screened is None:
                        self.plans.pop(entity.id)
                        # A visible handle does not make it reachable. The
                        # current measured panel may still offer a screened
                        # fingertip contact, as when no handle is visible.
                        points = self.scene.measurement_clouds.get(entity.id)
                        if points is not None and len(points) >= 40:
                            contact = self._surface_contact_plan(entity, points)
                            if contact is not None:
                                self.plans[entity.id] = contact
                        continue
                    self.plans[entity.id] = screened
                    self.candidate_diagnostics.append({'stage': 'fixture_contact_plan',
                        'anchor_id': entity.id, 'label': entity.name, 'plan': copy.deepcopy(self.plans[entity.id])})
            elif not entity.part_of and not entity.name.startswith("area ") and not entity.name.endswith("surface"):
                contact = self.grasp_geometry(entity)
                if contact is not None:
                    self.plans[entity.id] = contact
        candidates = []
        options = []
        def add(skill, **parameters):
            if self.request_consequence_workers > 1:
                options.append((skill, parameters))
                return
            candidate = self._candidate(skill, parameters, screen_options=screen_options)
            if candidate is not None:
                candidates.append(candidate)
        for entity in entities:
            if entity.id == self.held:
                add('align', anchor_id=entity.id)
            if self.held is None and (entity.id in self.plans or entity.visible):
                for approach in ("above", "front", "left", "right"):
                    for path in ("direct", "over", "around"):
                        add("move_to", anchor_id=entity.id, approach=approach, path=path)
            if entity.id in self.plans and self.held is None:
                for skill in ("align", "descend", "lift"):
                    add(skill, anchor_id=entity.id)
            if entity.id != self.held:
                add("carry_to", target_id=entity.id)
                add("lower", target_id=entity.id)
            if self.allow_vla:
                if entity.visible:
                    for mode in fixture_actions(entity.name) or ("pick",):
                        add("call_vla", anchor_id=entity.id, mode=mode)
                if self.held and entity.id != self.held:
                    for mode in ("on", "in"):
                        add("call_vla", anchor_id=self.held, target_id=entity.id, mode=mode)
        add("set_gripper", mode="open")
        add("set_gripper", mode="close")
        if measured_robot(self.p)["gripper_opening_m"] < .075 or self.held:
            add("release")
        for angle in (-90, -45, 45, 90):
            add("rotate_wrist", angle_deg=angle, **({"anchor_id": self.active} if self.active else {}))
        for axis in "xyz":
            for distance in (-.02, -.01, .01, .02):
                add("nudge", axis=axis, distance_m=distance, **({"anchor_id": self.active} if self.active else {}))
        for mode in ("refresh", "wrist_scan"):
            add("observe", mode=mode)
        add("finish")
        add("ask_help")
        if self.request_consequence_workers > 1:
            from robots.libero.bounded_cpu_planning import request_candidates

            candidates = request_candidates(self, options, self.request_consequence_workers)
        from robots.libero.v5_state import relations
        right, front = self.scene.view_axes
        public_relations = []
        relation_entities = [self.target_cache.get(e.id, e)
            if (self.held is not None and e.id != self.held)
                or (not e.visible and self._has_anchor(e)) else e for e in self.scene.entities.values()]
        for row in relations(relation_entities, right_axis=right, front_axis=front):
            _, source, relation, target = row.split()
            public_relations.append({"source_id": source, "relation": relation, "target_id": target})
        published = self.memory.apply(candidates)
        compact = [compact_candidate(c) for c in published] if self.compact_infeasible_candidates_v1 else published
        self.candidate_compaction = {'before_count': len(published), 'after_count': len(compact),
            'blocked_markers': sum(c['consequences']['screen_scope'] == 'blocked_at_current_prefix' for c in compact),
            'before_json_bytes': len(json.dumps(published, separators=(',', ':')).encode()),
            'after_json_bytes': len(json.dumps(compact, separators=(',', ':')).encode())}
        request = {"schema_version": VERSION, "kind": "request", "observation_id": f"public-{self.revision}",
            "revision": self.revision, "instruction": self.ex.instruction,
            "remaining_sim_steps": self.p.env.execution_budget()["remaining_sim_steps"],
            "anchors": self.anchors(), "robot": self.robot(), "candidates": compact,
            "receipts": self.receipts[-3:], "relations": public_relations, "max_actions": k,
            "execution_prefix": None}
        validate(request)
        self.latest_request = request
        return request

    def snapshot_decision_context(self, *, remaining_reference_s=None):
        """Freeze only public data; no environment access in the worker."""
        if self._base_geometry is None:
            self._cloud_and_ik()
        state = measured_robot(self.p)
        budget = dict(self.p.env.execution_budget())
        cloud, _ = self._base_geometry
        clone = copy.copy(self)
        clone.scene = SimpleNamespace(entities=copy.deepcopy(self.scene.entities),
            measurement_clouds=dict(self.scene.measurement_clouds),
            measurement_clouds_by_view=copy.deepcopy(getattr(self.scene, 'measurement_clouds_by_view', {})),
            dual_view_fusion_v1=self.scene.dual_view_fusion_v1,
            view_axes=self.scene.view_axes, _scores=dict(self.scene._scores))
        obs = {"robot0_eef_pos": state["eef_xyz_m"], "robot0_eef_quat": state["eef_quat_xyzw"],
            "robot0_joint_pos": state["joint_positions_rad"],
            "robot0_gripper_qpos": state['finger_positions_m']}
        clone.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs, execution_budget=lambda: budget))
        clone.ex = SimpleNamespace(instruction=self.ex.instruction)
        clone._screen_cache = {}
        clone._base_geometry = cloud, PublicPoseScreen(self.robot_xml, state["joint_positions_rad"],
            state["eef_xyz_m"], state["eef_quat_xyzw"], self.geometry["site_offset_in_gripper_m"], warm_start=True)
        clone.plans = copy.deepcopy(self.plans)
        clone.candidate_diagnostics = []
        clone._instance_cache = dict(self._instance_cache)
        clone.instance_boundary_evidence = copy.deepcopy(self.instance_boundary_evidence)
        clone.record_public_geometry = False  # The worker never writes state artifacts.
        clone.public_geometry_evidence = {}
        clone.target_cache = dict(self.target_cache)
        clone.memory = copy.deepcopy(self.memory)
        template = copy.deepcopy(self.latest_request)
        template['execution_prefix'] = None
        template['anchors'] = clone.anchors()
        template['receipts'] = copy.deepcopy(self.receipts[-3:])
        template["robot"] = clone.robot()
        template["remaining_sim_steps"] = budget["remaining_sim_steps"]
        template["revision"] = self.revision+1
        template["observation_id"] = f"prefetch-{self.revision+1}-step{budget['used_sim_steps']}"
        committed = copy.deepcopy(self._executing_prefix)
        def build_request():
            request = copy.deepcopy(template)
            future = clone
            if committed is not None:
                remaining = committed['choices'][committed['completed']:]
                if remaining:
                    prediction = PublicPrefixPrediction(clone, template)
                    for candidate in remaining:
                        endpoint = committed.get('motion_endpoints', {}).get(candidate['id'])
                        resolved = candidate if endpoint is not None else prediction.candidate(candidate)
                        if resolved is None:
                            raise ValueError('committed prefix lost its measured route')
                        prediction.advance(resolved, commanded_endpoint=endpoint)
                    future = prediction.adapter
                    expected_budget = (prediction.budget['remaining_sim_steps'] if remaining_reference_s is None
                        else max(0, budget['remaining_sim_steps']-math.ceil(remaining_reference_s*self.config.hz)))
                    prediction.budget['remaining_sim_steps'] = expected_budget
                    predicted_anchors = copy.deepcopy(template['anchors'])
                    for anchor in predicted_anchors:
                        entity = future.scene.entities[anchor['id']]
                        anchor.update(xyz_m=list(entity.xyz),
                            size_m=(np.asarray(entity.upper)-entity.lower).tolist())
                    predicted_robot = future.robot()
                    predicted_robot['velocity_m_s'] = [0., 0., 0.]  # Conditional rest endpoint, not a measurement.
                    request['execution_prefix'] = dict(
                        source_observation_id=committed['request']['observation_id'],
                        source_revision=committed['request']['revision'],
                        steps=[{key: c[key] for key in ('id', 'skill', 'parameters')} for c in remaining],
                        predicted_state=dict(robot=predicted_robot, anchors=predicted_anchors,
                            remaining_sim_steps=expected_budget), assumptions=list(prediction.assumptions))
            request["candidates"] = [candidate for c in template["candidates"]
                if (candidate := future._candidate(c["skill"], c["parameters"])) is not None]
            request["candidates"] = future.memory.apply(request["candidates"])
            if self.compact_infeasible_candidates_v1:
                request['candidates'] = [compact_candidate(c) for c in request['candidates']]
            validate(request)
            return request
        return {"sim_step": budget["used_sim_steps"], "build_request": build_request}

    def adopt_prefetched(self, request, decision=None):
        """Recheck measured targets before accepting a readonly prefetch."""
        self.last_prefetch_adoption = None
        if request["revision"] != self.revision:
            return False
        exact = (request['robot'] == self.robot()
                and request['remaining_sim_steps'] == self.p.env.execution_budget()['remaining_sim_steps']
                and request['receipts'] == self.receipts[-3:])
        prefix = request['execution_prefix']
        anchors = request['anchors']
        if not exact:
            chunk = self._last_free_chunk
            # A moving prefetch necessarily predates the endpoint's robot,
            # budget and successful motion receipts. It remains an honest
            # earlier observation: do not relabel those measurements as new.
            # Only the just-completed free-motion chunk may bridge that age;
            # contact/failure cannot be predicted by a pre-contact request.
            if (decision is None or chunk is None or prefix is None or chunk['revision']+1 != self.revision
                    or prefix['source_revision'] != chunk['revision']
                    or prefix['source_observation_id'] != chunk['observation_id']
                    or [step['id'] for step in prefix['steps']] != chunk['selected_ids'][-len(prefix['steps']):]
                    or request['receipts'] != chunk['parent_receipts']
                    or not (self.p.env.execution_budget()['remaining_sim_steps']
                        <= request['remaining_sim_steps'] <= chunk['remaining_sim_steps'])
                    or chunk['end_robot'] != self.robot()):
                return False
            predicted = prefix['predicted_state']
            expected_robot, actual_robot = predicted['robot'], self.robot()
            if (expected_robot['held_anchor_id'] != actual_robot['held_anchor_id']
                    or np.linalg.norm(np.asarray(expected_robot['eef_xyz_m'])-actual_robot['eef_xyz_m'])
                        > self.config.endpoint_tolerance_m
                    or (Rotation.from_quat(expected_robot['eef_quat_xyzw'])
                        *Rotation.from_quat(actual_robot['eef_quat_xyzw']).inv()).magnitude() > .05):
                return False
            anchors = predicted['anchors']
        elif prefix is not None:
            # An in-flight promise is accepted only through its completed,
            # successful source chunk, even if measured poses happen to agree.
            return False
        if self.receipts and self.receipts[-1]["outcome"] != "success":
            return False
        for anchor in anchors:
            current = self.scene.entities.get(anchor["id"])
            if current is None or np.linalg.norm(np.asarray(current.xyz)-anchor["xyz_m"]) > .01:
                return False
            if not current.visible and not (current.geometry and current.geometry.startswith("cached_perception")):
                return False
        validate(request)
        if not exact:
            current_choices = []
            for candidate in selected(request, decision):
                current = self._candidate(candidate['skill'], candidate['parameters'])
                if current is None or not self.memory.apply([current]):
                    return False
                consequence = current['consequences']
                if consequence['collision'] is True or consequence['ik_reachable'] is False:
                    return False
                current_choices.append(current)
            cost = sum(c['consequences']['expected_steps'] or 0 for c in current_choices)
            if cost > self.p.env.execution_budget()['remaining_sim_steps']:
                return False
            self.last_prefetch_adoption = {
                'source_observation_id': request['observation_id'],
                'source_remaining_sim_steps': request['remaining_sim_steps'],
                'current_remaining_sim_steps': self.p.env.execution_budget()['remaining_sim_steps'],
                'rechecked_candidate_ids': [c['id'] for c in current_choices],
                'source_measurements_preserved': True}
        self.latest_request = request
        return True

    def prefix_context(self, request, prefix):
        """Compute public consequences for any chosen prefix, without stepping."""
        prediction = PublicPrefixPrediction(self, request)
        for cid in prefix:
            candidate = prediction.candidate(prediction.original[cid])
            if candidate is None:
                raise ValueError('prefix references an unmeasured route')
            prediction.advance(candidate)
        return prediction.context()

    def plan_chunk(self, request, decision):
        """Screen the selected sequence using its predicted predecessor states."""
        prediction = PublicPrefixPrediction(self, request)
        plan = []
        for original in selected(request, decision):
            candidate = prediction.candidate(original)
            if candidate is None:
                candidate = copy.deepcopy(original)
            plan.append({'prefix': list(prediction.prefix), 'candidate': candidate,
                'predicted_robot': prediction.adapter.robot(),
                'predicted_anchors': {key: list(entity.xyz)
                    for key, entity in prediction.adapter.scene.entities.items()},
                'conditional_on': copy.deepcopy(prediction.assumptions)})
            if is_boundary(candidate) or candidate['consequences']['screen_scope'] == 'conditional_on_prefix':
                break
            prediction.advance(candidate)
        return plan

    def _free_motion(self, candidate):
        """Contact still permits a suffix, but requires a measured checkpoint."""
        skill = candidate['skill']
        return (skill in MOTION_SKILLS and skill not in {'descend', 'lower', 'lift'}
            and not (skill in {'nudge', 'rotate_wrist'} and (
                candidate['parameters'].get('anchor_id') or any(
                    check['anchor_id'] is not None for check in candidate['expected_receipt']))))

    def execute(self, request, decision, *, async_decisions=None):
        choices = selected(request, decision)
        self._executing_prefix = ({'request': request, 'choices': choices, 'completed': 0}
            if all(self._free_motion(c) for c in choices) else None)
        try:
            return self._execute_chunk(request, decision, choices, async_decisions=async_decisions)
        finally:
            self._executing_prefix = None

    def _execute_chunk(self, request, decision, choices, *, async_decisions=None):
        if self.latest_request is not request:
            raise ValueError("request is not the adapter's current observation")
        free_chunk = all(self._free_motion(c) for c in choices)
        parent_receipts = copy.deepcopy(self.receipts[-3:])
        remaining_at_start = self.p.env.execution_budget()['remaining_sim_steps']
        plan = self.plan_chunk(request, decision)
        # Freeze actual current surfaces before controls. A selected contact
        # prefix can move an anchor; its later guard must compare fresh depth
        # with that conditionally translated surface, not an old SAM centre.
        reference_keys = {key for row in plan for key in (
            row['candidate']['parameters'].get('anchor_id'),
            row['candidate']['parameters'].get('target_id'),
            *(check['anchor_id'] for check in row['candidate']['expected_receipt']))
            if key is not None and key != self.held}
        references = {key: np.array(self._contact_pixels(key), copy=True)
            for key in sorted(reference_keys)}
        self.details.append({'chunk_plan': plan, 'prediction_is_measurement': False,
            'anchor_surface_references': {key: {
                'points': len(points), 'capture_step': self.ex.toolkit._state.latest_step,
                'artifact': self._record_public_geometry('bounded_chunk_reference_'+key, points)}
                for key, points in references.items()}})
        lookahead = async_decisions if free_chunk else None
        outcomes, cursor = [], 0
        while cursor < len(plan):
            if self._executing_prefix is not None:
                self._executing_prefix['completed'] = cursor
            row = plan[cursor]
            candidate = row['candidate']
            # Reusing a measured anchor is allowed; an unexplained fresh move
            # of that anchor invalidates the prediction before its suffix.
            parameters = candidate['parameters']
            keys = [parameters.get('anchor_id'), parameters.get('target_id')]
            if candidate['skill'] in {'nudge', 'rotate_wrist'}:
                keys += [check['anchor_id'] for check in candidate['expected_receipt']]
            keys = list(dict.fromkeys(keys))
            stale_keys = [key for key in keys if key is not None and key != self.held
                and key in row['predicted_anchors']
                and (entity := self.scene.entities.get(key)) is not None and entity.visible
                and np.linalg.norm(np.asarray(entity.xyz)-row['predicted_anchors'][key]) > .01]
            stale = None
            for key in stale_keys:
                # Moving the wrist changes a partial SAM centre even when
                # the clean pre-approach surface is still in the same place.
                # Preserve the 1cm movement gate, but test actual RGB-D
                # surface displacement before treating that centre as motion.
                reference = references.get(key)
                recheck = {'accepted': False, 'reason': 'pre_action_surface_missing'}
                if reference is not None and len(reference) >= 40:
                    from robots.libero.bounded_payload import stationary_surface_registration

                    shift = (np.asarray(row['predicted_anchors'][key])
                        -plan[0]['predicted_anchors'][key])
                    self._cloud_and_ik(key, contact=True)
                    recheck = stationary_surface_registration(reference+shift,
                        self._base_geometry[0], self._contact_pixels(key))
                    recheck['conditional_prefix_translation_m'] = shift.tolist()
                self.details.append({'anchor_recheck': recheck, 'anchor_id': key,
                    'predicted_xyz_m': row['predicted_anchors'][key],
                    'current_visible_centre_xyz_m': list(self.scene.entities[key].xyz)})
                if not recheck['accepted']:
                    stale = key
                    break
            if stale is not None:
                robot = self.robot()
                receipt = dict(schema_version=VERSION, kind='receipt', observation_id=request['observation_id'],
                    candidate_id=candidate['id'], skill=candidate['skill'], outcome='failure', phase='perception',
                    stop_reason='predicted_anchor_changed', steps_used=0, before=robot, after=robot,
                    changes=[], evidence=[self._evidence(self.scene.entities[stale])], expectation_checks=[])
                self.receipts.append(receipt)
                self.memory.record(candidate, receipt['outcome'], receipt['stop_reason'])
                outcomes.append(receipt)
                break
            group = []
            for following in plan[cursor:]:
                if not self._free_motion(following['candidate']):
                    break
                group.append(following['candidate'])
            if len(group) > 1:
                receipts = self._execute_motion_group(request, group, lookahead=lookahead)
                outcomes.extend(receipts)
                cursor += len(receipts)
                if len(receipts) < len(group) or any(r['outcome'] != 'success' for r in receipts):
                    break
            else:
                receipt = self._execute_one(request, candidate, lookahead=lookahead)
                outcomes.append(receipt)
                self.receipts.append(receipt)
                self.memory.record(candidate, receipt['outcome'], receipt['stop_reason'])
                cursor += 1
                if receipt['outcome'] != 'success' or is_boundary(candidate):
                    break
            if self.p.env.terminated or self.p.env.truncated:
                break
        executed = [r['candidate_id'] for r in outcomes]
        self.last_chunk = {'schema_version': VERSION, 'selected_ids': decision['candidate_ids'],
            'executed_ids': executed, 'actual_actions': sum(r['steps_used'] > 0 for r in outcomes),
            'discarded_ids': decision['candidate_ids'][len(executed):],
            'stop_reason': outcomes[-1]['stop_reason'] if outcomes else 'no_predicted_route',
            'interrupted_skill': outcomes[-1]['skill'] if outcomes and len(executed) < len(choices) else None}
        self.revision += 1
        self._last_free_chunk = ({'revision': request['revision'], 'parent_receipts': parent_receipts,
            'observation_id': request['observation_id'], 'selected_ids': decision['candidate_ids'],
            'remaining_sim_steps': remaining_at_start, 'end_robot': self.robot()}
            if free_chunk and len(outcomes) == len(choices)
                and all(r['outcome'] == 'success' for r in outcomes) else None)
        return outcomes

    def _execute_motion_group(self, request, candidates, *, lookahead=None):
        """Blend adjacent free motions; report each waypoint's measured passage."""
        before_group, entities_before = self.robot(), dict(self.scene.entities)
        robot = measured_robot(self.p)
        waypoints, boundaries = [], []
        for candidate in candidates:
            self._commit_grasp(candidate)
            route = self._route(candidate["skill"], candidate["parameters"], robot=robot)
            if route is None:
                raise ValueError("chunk anchor became unmeasured")
            waypoints.extend(route)
            boundaries.append(len(waypoints)-1)
            robot = {**robot, "eef_xyz_m": route[-1]["xyz_m"], "eef_quat_xyzw": route[-1]["quat_xyzw"]}
        if self._executing_prefix is not None:
            # Public endpoints of the actual screened trajectory, frozen before
            # the first control command. Never replay a relative delta twice.
            self._executing_prefix['motion_endpoints'] = {
                c['id']: copy.deepcopy(waypoints[b]) for c, b in zip(candidates, boundaries)}
            offset = self._executing_prefix['completed']
            self._executing_prefix['choices'][offset:offset+len(candidates)] = candidates
        motion = SmoothMotion(self.p, self._cloud_and_ik(), self.config)
        boundary_loss = None
        boundary_hold = []
        group_offset = self._executing_prefix['completed'] if self._executing_prefix is not None else 0
        def check_waypoint(index, measured):
            nonlocal boundary_loss
            if index not in boundaries:
                return None
            waypoint = waypoints[index]
            if np.linalg.norm(np.asarray(measured['eef_xyz_m'])-waypoint['xyz_m']) > self.config.endpoint_tolerance_m:
                return 'endpoint_error_m'
            if (Rotation.from_quat(measured['eef_quat_xyzw'])*Rotation.from_quat(waypoint['quat_xyzw']).inv()).magnitude() > .05:
                return 'angular_error_rad'
            if self.held:
                self.refresh()
                holding, lost = self._recheck_transport_hold(before_group, entities_before)
                boundary_hold.append({'waypoint_index': index, 'evidence': holding})
                if lost is not None:
                    boundary_loss = (index, lost)
                    return 'public_hold_lost'
            if self._executing_prefix is not None:
                self._executing_prefix['completed'] = group_offset+boundaries.index(index)+1
            return None
        result = motion.run(waypoints, gripper=self.gripper_command, blend=True,
            lookahead=lookahead, request_factory=self.snapshot_decision_context if lookahead is not None else None,
            contact_stop=self._empty_held_gripper, waypoint_check=check_waypoint)
        self.refresh()
        holding, lost_held = self._recheck_transport_hold(before_group, entities_before)
        if boundary_loss is not None:
            lost_held = boundary_loss[1]
        trace = result.get("trace", [])
        interrupted_at = next((check['index'] for check in result.get('checked_waypoints', []) if check['failure']), None)
        cursor, receipts = 0, []
        for candidate, boundary in zip(candidates, boundaries):
            target = np.asarray(waypoints[boundary]["xyz_m"])
            # Desired passage partitions the executed stream. It is not an
            # extra servo stop, nor a claim the actual pose hit the waypoint.
            if trace:
                candidates_i = range(cursor, len(trace))
                passage_time = result['waypoint_times_s'][boundary]
                at = min(candidates_i, key=lambda i: abs(trace[i]['time_s']-passage_time)) if cursor < len(trace) else len(trace)-1
                if boundary == interrupted_at:
                    at = len(trace)-1  # The failed step owns its braking tail.
                segment = trace[cursor:at+1]
                after_raw = trace[at]["after"]
                before_raw = segment[0]["before"] if segment else after_raw
                error = float(np.linalg.norm(np.asarray(after_raw["eef_xyz_m"])-target))
                angular_error = float((Rotation.from_quat(after_raw['eef_quat_xyzw'])*
                    Rotation.from_quat(waypoints[boundary]['quat_xyzw']).inv()).magnitude())
                cursor = at+1
                def sensor(raw):
                    return {k: raw[k] for k in ("eef_xyz_m", "eef_quat_xyzw", "gripper_opening_m")} | {
                        "held_anchor_id": before_group['held_anchor_id'], "velocity_m_s": None}
                before, after = sensor(before_raw), sensor(after_raw)
            else:
                segment, error, angular_error, before, after = [], float("inf"), float('inf'), request["robot"], self.robot()
            outcome = "success" if error <= self.config.endpoint_tolerance_m and angular_error <= .05 else "failure"
            reason = "measured_waypoint_passage" if outcome == "success" else (
                'angular_waypoint_not_reached' if error <= self.config.endpoint_tolerance_m else result["stop_reason"])
            terminal_passage = bool(segment) and cursor == len(trace) and (self.p.env.terminated or self.p.env.truncated)
            if terminal_passage and self.p.env.terminated:
                outcome, reason = 'success', 'native_success'
            endpoint_loss = lost_held is not None and (
                boundary_loss is not None and boundary == boundary_loss[0]
                or boundary_loss is None and (cursor == len(trace) or candidate is candidates[-1]))
            phase = None if outcome == 'success' else 'planning_unreachable'
            if endpoint_loss:
                outcome, phase, reason = 'failure', 'contact_failure', 'public_hold_lost'
                after = {**after, 'held_anchor_id': None}
            receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
                "candidate_id": candidate["id"], "skill": candidate["skill"], "outcome": outcome,
                "phase": phase, "stop_reason": reason,
                "steps_used": len(segment), "before": before, "after": after,
                "changes": ([{'anchor_id': lost_held, 'displacement_m': None, 'held': False,
                    'relation': None, 'fixture_state': None}] if endpoint_loss else []),
                "evidence": [self._evidence(e) for e in self.scene.entities.values()]}
            check_receipt(candidate, receipt, {'endpoint_error_m': error, 'angular_endpoint_error_rad': angular_error})
            validate(receipt)
            receipts.append(receipt)
            self.receipts.append(receipt)
            self.memory.record(candidate, receipt['outcome'], receipt['stop_reason'])
            if terminal_passage or endpoint_loss or receipt['outcome'] != 'success':
                break
        self.details.append({"candidate_ids": [c["id"] for c in candidates], "execution": result,
                             "blended": True, "waypoint_errors_are_measured": True,
                             "public_transport_hold": holding, "boundary_hold_checks": boundary_hold})
        return receipts

    def _execute_one(self, request, candidate, *, lookahead=None):
        before = self.robot()
        start_steps = self.p.env.execution_budget()["used_sim_steps"]
        entities_before = dict(self.scene.entities)
        observed_before = self.previous_scene | {
            eid: np.asarray(entity.xyz) for eid, entity in entities_before.items() if entity.visible}
        skill, parameters = candidate["skill"], candidate["parameters"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        if key is None and skill in {'nudge', 'rotate_wrist'}:
            key = self.active
        phase, outcome, reason, detail = None, "unmeasured", "measurement_missing", {}
        contact_reference = None
        contact_capture_step = None
        if skill == 'nudge' and key is not None:
            contact_capture_step = self.ex.toolkit._state.latest_step
            screen = self._cloud_and_ik(key, contact=True)
            handle = self.plans.get(key, {}).get('handle_measurement')
            if key == self.held:
                # Held geometry is deliberately removed from stationary
                # screen.target. Register its measured moving surface,
                # expressed in world coordinates, rather than an empty set.
                robot = measured_robot(self.p)
                contact_reference = (screen.payload
                    @ Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T
                    + robot['eef_xyz_m'])
            elif handle:
                from scipy.spatial import cKDTree

                # A committed handle can predate the current capture. Reuse
                # its currently observed depth matches from collision
                # screening, without adding the stationary parent surface.
                contact_reference = self._contact_pixels(key, handle_only=True)
                present = cKDTree(self._base_geometry[0]).query(contact_reference,
                    distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                contact_reference = contact_reference[present]
            else:
                contact_reference = np.array(screen.target, copy=True)
            self._record_public_geometry(f'bounded_contact_{key}_reference', contact_reference)
        if skill in MOTION_SKILLS:
            payload_reference = None
            if skill == 'lift' and self.grasp_reference is not None and self.held is None:
                payload_reference = self._capture_payload_reference(key)
            self._commit_grasp(candidate)
            route = self._route(skill, parameters)
            if route is None:
                phase, outcome, reason = "perception", "failure", "current_anchor_unmeasured"
            else:
                motion = SmoothMotion(self.p, self._cloud_and_ik(key, contact=skill in {"descend", "lower", "nudge"}
                    or (skill in {"lift", "rotate_wrist"} and self.active is not None)), self.config)
                detail = motion.run(route, gripper=self.gripper_command, lookahead=lookahead,
                    request_factory=self.snapshot_decision_context if lookahead is not None else None,
                    contact_stop=self._empty_held_gripper)
                reason = detail["stop_reason"]
                angular_error = (Rotation.from_quat(route[-1]["quat_xyzw"])*Rotation.from_quat(self.robot()["eef_quat_xyzw"]).inv()).magnitude()
                detail["angular_endpoint_error_rad"] = float(angular_error)
                outcome = "success" if (detail.get("endpoint_error_m", 1.) <= self.config.endpoint_tolerance_m
                    and angular_error <= .05 and detail["stop_reason"] in {"endpoint", "native_stop", "decision_pending_at_rest_endpoint"}) else "failure"
                phase = None if outcome == "success" else ("collision" if "collision" in reason else "planning_unreachable")
                if skill == 'descend' and outcome == 'success':
                    self.active = key
                    self.withdrawal_contact = None
                if outcome != 'success':
                    if skill == 'descend' and detail.get('executed') and key in self.committed_grasps:
                        # A partial descent can already touch the selected
                        # measured surface. Preserve that identity for a
                        # screened withdrawal without claiming a grasp.
                        self.withdrawal_contact = copy.deepcopy(self.committed_grasps[key]) | {'anchor_id': key}
                        limits = getattr(getattr(motion.screen, 'ik', None), 'limits', None)
                        if limits is not None:
                            joints = np.asarray(measured_robot(self.p)['joint_positions_rad'])
                            margin = float(np.minimum(joints-limits[:, 0], limits[:, 1]-joints).min())
                            if margin < .02:
                                self.failed_contact_poses.setdefault(key, []).append({
                                    **copy.deepcopy(self.plans[key]), 'measured_joint_margin_rad': margin})
                    # A rejected nudge issues no control and cannot break
                    # measured contact. Keep its handle identity through
                    # the recovery decision instead of inventing obstacles
                    # at the unchanged fingers after a zero-step rejection.
                    if skill != 'nudge' or detail.get('executed'):
                        self.committed_grasps.pop(key, None)
        elif skill in {"release", "set_gripper"}:
            opening = skill == "release" or parameters.get("mode") == "open"
            if opening:
                prior_contact = self.active or self.held
                if prior_contact in self.committed_grasps:
                    self.withdrawal_contact = copy.deepcopy(self.committed_grasps[prior_contact]) | {
                        'anchor_id': prior_contact}
                    points = self._cloud_and_ik(prior_contact, contact=True).target
                    if len(points):
                        self.withdrawal_contact['withdrawal_surface'] = {
                            'xyz_world': np.array(points, copy=True),
                            'source_step': self.ex.toolkit._state.latest_step}
            self.gripper_command = -1. if opening else 1.
            prior = before["gripper_opening_m"]
            detail = {'trace': []}
            for _ in range(15):
                if self.p.env.terminated or self.p.env.truncated:
                    break
                action = np.r_[np.zeros(6), self.gripper_command]
                sensor_before, sensor_after = public_control(self.p, action)
                detail['trace'].append({'before': sensor_before, 'after': sensor_after,
                    'action': action.tolist()})
            detail['steps_used'] = len(detail['trace'])
            current = measured_robot(self.p)["gripper_opening_m"]
            outcome = "success" if abs(current-prior) >= .003 else "no_effect"
            reason = "measured_gripper_change" if outcome == "success" else "no_measured_change"
            if opening:
                self.held = None
                self.active = None
                self.grasp_reference = None
                self.payload_reference = None
                self.committed_grasps.clear()
        elif skill == "observe":
            outcome, reason = "success", "fresh_public_views"
            if parameters["mode"] == "wrist_scan":
                contact = self.active or (self.withdrawal_contact or {}).get('anchor_id')
                motion = SmoothMotion(self.p, self._cloud_and_ik(contact, contact=contact is not None), self.config)
                attempts = []
                for offset in ([0., 0., .04], [.04, 0., 0.], [-.04, 0., 0.], [0., .04, 0.], [0., -.04, 0.]):
                    point = np.asarray(before['eef_xyz_m'])+offset
                    detail = motion.run([{'xyz_m': point.tolist()}], gripper=self.gripper_command)
                    attempts.append({'offset_m': offset, 'stop_reason': detail['stop_reason'],
                        'executed': detail['executed'], 'screen': detail.get('screen')})
                    # Only try another direction after an unexecuted route
                    # rejection. Actual movement always returns to sensing.
                    if detail.get('executed') or self.p.env.terminated or self.p.env.truncated:
                        break
                detail['scan_route_attempts'] = attempts
                if not detail.get("executed") or detail["stop_reason"] not in {"endpoint", "native_stop"}:
                    outcome, reason = "failure", detail["stop_reason"]
                    phase = "collision" if "collision" in reason else "planning_unreachable"
                elif detail.get('endpoint_error_m', float('inf')) > self.config.endpoint_tolerance_m:
                    outcome, reason, phase = 'failure', 'scan_waypoint_not_reached', 'planning_unreachable'
        elif skill == "call_vla":
            detail = self.call_vla(parameters)
            outcome, reason = detail["outcome"], detail["stop_reason"]
            phase = None if outcome == "success" else "contact_failure"
        elif skill == "finish":
            outcome = "success" if self.p.env.terminated else "rejected"
            reason = "native_success" if outcome == "success" else "environment_reports_task_incomplete"
        elif skill == "ask_help":
            outcome, reason = "rejected", "no_human_available_use_observe_restage_or_other_approach"
        if skill == 'nudge' and key is not None and outcome == 'success':
            contact_registration = self.refresh(contact_motion=(key, parameters['axis'],
                parameters['distance_m'], contact_reference, contact_capture_step))
        else:
            self.refresh()
            contact_registration = None
        lost_held = None
        if skill in MOTION_SKILLS:
            holding, lost_held = self._recheck_transport_hold(before, entities_before)
            detail['public_transport_hold'] = holding
            if lost_held is not None:
                outcome, phase, reason = 'failure', 'contact_failure', 'public_hold_lost'
        if skill == 'observe':
            if (parameters['mode'] == 'wrist_scan' and self.held is None
                    and np.linalg.norm(np.asarray(self.robot()['eef_xyz_m'])-before['eef_xyz_m'])
                    > self.config.endpoint_tolerance_m):
                # A measured scan withdrawal breaks unverified surface
                # contact. Do not let the next nudge act on its old identity
                # while the hand is now above the object.
                self.active = None
                self.grasp_reference = None
                # Displacement alone does not establish separation from a
                # tall panel. Retain its stationary measured identity for
                # subsequent screened withdrawals; _contact_pixels still
                # requires matching CURRENT depth and cannot attach it to
                # the moving hand. A new descent replaces this reference.
                if not self.withdrawal_contact or 'withdrawal_surface' not in self.withdrawal_contact:
                    self.withdrawal_contact = None
                self.committed_grasps.clear()
            elif self.active is None:
                self.committed_grasps.clear()
            # A passive refresh or an unexecuted scan has not broken the
            # measured contact. Keep its public patch through jaw occlusion;
            # losing it here can remove every lift after a successful close.
        if skill == 'set_gripper' and parameters.get('mode') == 'close' and self.active:
            if self.active in self.committed_grasps:
                self.committed_grasps[self.active]['contact_robot'] = measured_robot(self.p)
            contact_entity = self.scene.entities.get(self.active)
            # Closing can move an object and change its visible surface.
            # Test subsequent lift coupling against the post-close sample,
            # never against an image captured before descent/contact.
            self.grasp_reference = (copy.deepcopy(contact_entity), self.robot()) if contact_entity and contact_entity.visible else None
        if skill == "observe" and outcome == "success":
            # Moving the camera alone cannot reset recovery failures. A scan
            # must reveal an entity or a measured scene change; otherwise
            # repeated upward scans can consume the entire episode.
            changed = any(eid in self._last_scene_changes and (eid not in observed_before
                or np.linalg.norm(np.asarray(entity.xyz)-observed_before[eid]) >= .01
                ) for eid, entity in self.scene.entities.items() if entity.visible)
            if not changed:
                outcome, reason = "no_effect", "no_measured_scene_change"
        if skill == 'nudge' and key is not None and outcome == 'success':
            prior = entities_before.get(key)
            current = self.scene.entities.get(key)
            measured = (prior is not None and prior.visible and current is not None
                and current.visible and current.source_step > prior.source_step)
            displacement = np.asarray(current.xyz)-prior.xyz if measured else None
            progress = (float(displacement['xyz'.index(parameters['axis'])]
                * np.sign(parameters['distance_m'])) if measured else None)
            registration = contact_registration
            after_capture_step = self.ex.toolkit._state.latest_step
            fresh_depth = after_capture_step > contact_capture_step
            detail['public_contact_motion'] = {
                'source': 'paired_public_rgbd_axis_surface_registration',
                'before_capture_step': contact_capture_step,
                'after_capture_step': after_capture_step,
                'entity_measurement_current': measured,
                'displacement_m': displacement.tolist() if measured else None,
                'command_axis': parameters['axis'], 'entity_axis_progress_m': progress,
                'axis_progress_m': (float(registration['translation_m']['xyz'.index(parameters['axis'])]
                    * np.sign(parameters['distance_m'])) if registration and registration['accepted'] else None),
                'minimum_progress_m': .005, 'surface_registration': registration}
            # EEF arrival alone says nothing about a contacted object moving.
            # Preserve free-space nudges and the benchmark's native success.
            if not self.p.env.terminated:
                if not fresh_depth or not registration['accepted']:
                    outcome, phase, reason = 'unmeasured', 'verification_error', 'contact_motion_unmeasured'
                else:
                    low, high = sorted(np.asarray(registration['compatible_axis_interval_m'])
                        * np.sign(parameters['distance_m']))
                    if low >= .005:
                        pass
                    elif high <= -.005:
                        outcome, phase, reason = 'failure', 'contact_failure', 'contact_motion_opposes_command'
                    elif low > -.005 and high < .005:
                        outcome, phase, reason = 'no_effect', 'contact_failure', 'contact_no_measured_progress'
                    else:
                        outcome, phase, reason = 'unmeasured', 'verification_error', 'contact_surface_motion_ambiguous'
            if (outcome in {'no_effect', 'failure', 'unmeasured'} and len(contact_reference) >= 40
                    and reason.startswith('contact_')):
                self._contact_retry_references[key] = (key, parameters['axis'], parameters['distance_m'],
                    contact_reference, contact_capture_step)
        if skill == "lift" and self.grasp_reference is not None:
            source, robot_at_contact = self.grasp_reference
            current = self.scene.entities.get(key)
            if source is not None and current is not None and current.visible:
                rise = current.lower[2]-source.lower[2]
                robot = self.robot()
                coupling = np.linalg.norm((np.array(current.xyz)-source.xyz)
                    -(np.array(robot["eef_xyz_m"])-robot_at_contact['eef_xyz_m']))
                holding = self._held_motion_evidence(source, current, robot_at_contact, robot)
                opening = robot["gripper_opening_m"]
                aperture, aperture_evidence = self.holding_aperture(opening)
                detail["public_hold"] = {"rise_m": rise, "relative_displacement_m": float(coupling),
                    "opening_m": opening, 'aperture': aperture_evidence, 'bounds_co_motion': holding}
                # Segmentation sees a different surface after the lift; its
                # centre is not a material point. Use the same EEF-transported
                # measured bounds as carry, with the unchanged 15 mm gap.
                if holding is None:
                    outcome, phase, reason = 'unmeasured', 'verification_error', 'lift_motion_unmeasured'
                elif rise >= .03 and not holding['lost'] and aperture:
                    self.held = key
                    if payload_reference is not None:
                        self.payload_reference = payload_reference
                else:
                    outcome, phase, reason = "failure", "contact_failure", "public_hold_not_verified"
            else:
                outcome, phase, reason = "unmeasured", "verification_error", "lifted_object_not_visible"
        if self.p.env.terminated:
            # Native completion is a public stop condition. Reaching it can
            # interrupt a wrist turn before its nominal waypoint; that is not
            # an execution failure. Truncation alone does not establish success.
            outcome, phase, reason = 'success', None, 'native_success'
        changes = [{"anchor_id": eid,
            "displacement_m": (np.asarray(entity.xyz)-entities_before[eid].xyz).tolist() if eid in entities_before and entity.visible else None,
            "held": False if eid == lost_held else eid == self.held if self.held else None,
            "relation": None, "fixture_state": None}
            for eid, entity in self.scene.entities.items()]
        receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
            "candidate_id": candidate["id"], "skill": skill, "outcome": outcome, "phase": phase,
            "stop_reason": reason, "steps_used": self.p.env.execution_budget()["used_sim_steps"]-start_steps,
            "before": before, "after": self.robot(), "changes": changes,
            "evidence": [self._evidence(entity) for entity in self.scene.entities.values()]}
        contact_motion = detail.get('public_contact_motion')
        if contact_motion and (fit := contact_motion['surface_registration']) and fit['accepted']:
            receipt['evidence'].append({
                'measurement_id': f'rgbd-contact:{contact_capture_step}:{after_capture_step}:{key}',
                'capture_step': after_capture_step, 'source': 'derived_public',
                'cameras': ['main', 'wrist'] if self.scene.dual_view_fusion_v1 else ['main'],
                'operation': (f"paired_contact_axis:{parameters['axis']}:compatible_interval_m="
                    + json.dumps(fit['compatible_axis_interval_m']))})
        check_receipt(candidate, receipt, detail)
        if (receipt['outcome'] == 'success' and (skill == 'nudge'
                or (skill == 'set_gripper' and parameters.get('mode') == 'close'))):
            self._update_contact_surface_reference(self.active)
        validate(receipt)
        self.details.append({"candidate_id": candidate["id"], "execution": detail})
        self.ex.held = self.held
        return receipt

    def _update_contact_surface_reference(self, anchor_id):
        """Advance a contacted handle from fresh public depth, never prediction."""
        committed = self.committed_grasps.get(anchor_id)
        if (self.p.env.terminated or self.held is not None or committed is None
                or not committed['plan'].get('handle_measurement')):
            return
        self._cloud_and_ik(anchor_id, contact=True)
        points = np.unique(self._contact_pixels(anchor_id, handle_only=True), axis=0)
        if len(points) < 40:
            return
        committed['contact_surface_reference'] = {
            'xyz_world': points.copy(), 'robot': measured_robot(self.p),
            'source_step': self.ex.toolkit._state.latest_step,
            'artifact': self._record_public_geometry('bounded_contact_'+anchor_id+'_tracked', points)}

    def _capture_payload_reference(self, anchor_id):
        """Retain a public capture before the next measured held-object move."""
        from scipy.spatial import cKDTree

        from robots.libero.v5_geometric_grasp import _voxel
        target = self._contact_pixels(anchor_id)
        self._cloud_and_ik(anchor_id, contact=True)
        scene = self._base_geometry[0]
        if len(target):
            # Remove exact target pixels before downsampling. Otherwise a
            # small held-object motion matches its own old surface and the
            # temporal static-scene veto rejects genuine payload pixels.
            member = cKDTree(target).query(scene,
                distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
            # The reference target must also exclude robot pixels from the
            # semantic mask, as the current measurement does during fitting.
            target = scene[member]
            scene = scene[~member]
        reference = {'target': np.array(target, copy=True),
            'scene': _voxel(scene, .001),
            'robot': measured_robot(self.p),
            'capture_step': self.ex.toolkit._state.latest_step}
        reference['artifacts'] = {name: self._record_public_geometry('bounded_payload_reference_'+name,
            reference[name]) for name in ('target', 'scene')}
        if self.record_public_geometry:
            self.ex.toolkit._state.save('bounded_payload_reference_robot.json', reference['robot'])
        return reference

    def _commit_grasp(self, candidate):
        if candidate['skill'] not in {'move_to', 'align', 'descend'}:
            return
        key = candidate['parameters']['anchor_id']
        if key not in self.committed_grasps and key in self.plans:
            entity = self.scene.entities[key]
            plan = self.plans[key]
            if candidate['skill'] == 'move_to' and 'surface_contact_options' in plan:
                plan = plan['surface_contact_options'][candidate['parameters']['approach']]
            plan = copy.deepcopy(plan)
            plan['contact_evidence'] = self._evidence(entity)
            self.plans[key] = plan
            self.committed_grasps[key] = {'plan': plan, 'anchor_xyz': np.array(entity.xyz)}
            if (self.precontact_instance_surface_v1 and not entity.part_of
                    and not fixture_actions(entity.name) and plan.get('contact_kind') != 'surface'):
                # Keep exact measured pixels: voxel centroids can lose the
                # millimetre-scale identity needed after jaw occlusion.
                points = self._instance_pixels(key)
                if len(points) >= 40:
                    from scipy.spatial import cKDTree

                    from robots.libero.v5_geometric_grasp import _voxel

                    self._cloud_and_ik(key, contact=True)
                    scene = self._base_geometry[0]
                    member = cKDTree(points).query(scene,
                        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
                    artifact = self._record_public_geometry(f'bounded_precontact_{key}_target', points)
                    self.committed_grasps[key]['instance_reference'] = {
                        'xyz_world': np.array(points, copy=True),
                        'stationary_scene': _voxel(scene[~member], .001),
                        'source_step': self.ex.toolkit._state.latest_step, 'artifact': artifact}

    def call_vla(self, parameters):
        if not self.allow_vla:
            raise ValueError("call_vla disabled for the oracle upper-bound diagnostic")
        source = self.scene.entities[parameters["anchor_id"]]
        mode = parameters["mode"]
        name = measured_instance_description(source, self.scene.entities, self.scene.view_axes)
        target = self.scene.entities.get(parameters.get("target_id"))
        target_name = measured_instance_description(target, self.scene.entities, self.scene.view_axes) if target else None
        prompt = f"pick up the {name}" if mode == "pick" else subtask_phrase(name, mode, target_name)
        initial = source
        initial_step = self.p.env.execution_budget()["used_sim_steps"]
        initial_endpoint = self.scene.measure_fixture_endpoint(source, name) if mode in {"open", "close"} else None
        initial_stove = self.ex.measure_stove(source) if mode in {"turn_on", "turn_off"} else None
        checks = []
        self.vla_trace = []
        hold_frames = []
        hold_verified = False
        vla_payload_reference = None
        def observe():
            nonlocal hold_verified, vla_payload_reference
            self.refresh()
            current = self.scene.entities.get(source.id)
            robot = self.robot()
            displacement = np.asarray(current.xyz)-initial.xyz if current and current.visible else np.full(3, np.nan)
            completed = False
            hold_evidence = None
            if mode == "pick" and current and current.visible:
                aperture, aperture_evidence = self.holding_aperture(robot['gripper_opening_m'])
                rise = current.lower[2]-initial.lower[2]
                raised = rise >= .03 and aperture
                if raised:
                    if vla_payload_reference is None:
                        # The first raised observation precedes the coupling
                        # check. Keep its RGB-D/EEF reference so the braking
                        # screen can identify the co-moving object's omitted
                        # edge pixels after the next observed movement.
                        vla_payload_reference = self._capture_payload_reference(source.id)
                    hold_frames.append((np.array(current.xyz), np.array(robot["eef_xyz_m"])))
                else:
                    hold_frames.clear()
                    hold_verified = False
                    vla_payload_reference = None
                hold_evidence = {'rise_m': rise, 'aperture': aperture_evidence,
                                 'relative_displacement_m': None, 'hand_displacement_m': None}
                if len(hold_frames) >= 2:
                    obj_before, hand_before = hold_frames[-2]
                    hand_delta = np.array(robot['eef_xyz_m'])-hand_before
                    coupling = float(np.linalg.norm((np.array(current.xyz)-obj_before)-hand_delta))
                    hold_evidence.update(relative_displacement_m=coupling,
                        hand_displacement_m=float(np.linalg.norm(hand_delta)))
                    hold_verified = coupling <= .015 and (hold_verified or np.linalg.norm(hand_delta) >= .005)
                    completed = hold_verified
                    if completed:
                        # Install measured ownership before run_fallback
                        # invokes handoff(), not only after braking. Otherwise
                        # held-object pixels are screened as scene obstacles.
                        self.held = self.active = source.id
                        self.payload_reference = vla_payload_reference
                        self._instance_cache.clear()
                        self._screen_cache.clear()
            elif mode == 'pick':
                hold_frames.clear()
                hold_verified = False
                vla_payload_reference = None
            elif mode in {"open", "close"}:
                from robots.libero.v5_verification import measured_fixture_endpoint
                state = self.scene.measure_fixture_endpoint(source, name)
                verdict, _ = measured_fixture_endpoint(initial_endpoint, state, mode,
                    drawer="drawer" in source.name or "cabinet" in source.name, signed_drawer_v6=True)
                completed = verdict is True
                if state.get("moving"):
                    displacement = np.array(state["moving"]["centre"])
            elif mode in {"turn_on", "turn_off"}:
                from robots.libero.v5_stove_measurement import measured_stove_endpoint
                stove = self.ex.measure_stove(source)
                verdict, _ = measured_stove_endpoint(initial_stove, stove, mode)
                completed = verdict is True
                displacement = np.array([float(stove.get("red_fraction", 0.)), 0., 0.])
            elif target and current and current.visible:
                from robots.libero.v5_verification import strict_place_verified_v6
                elapsed = (self.p.env.execution_budget()["used_sim_steps"]-initial_step)/self.config.hz
                completed = strict_place_verified_v6(initial, current, target, robot["gripper_opening_m"],
                    robot["eef_xyz_m"], elapsed, relation=mode) is True
            distance = float(np.linalg.norm(np.asarray(robot["eef_xyz_m"])-initial.xyz))
            # Moving toward a stationary object is progress during approach.
            progress = [*displacement.tolist(), distance]
            result = {"progress_vector_m": progress, "completed": bool(completed),
                      "outside_region": distance > .6, "evidence": [self._evidence(current)] if current else []}
            if mode == 'pick':
                result['public_hold'] = hold_evidence
            checks.append(result)
            return result
        def prepare():
            route = [{"xyz_m": self.preparation["eef_xyz_m"], "quat_xyzw": self.preparation["eef_quat_xyzw"]}]
            result = SmoothMotion(self.p, self._cloud_and_ik(), self.config).run(route, gripper=self.gripper_command)
            return {**result, "success": result.get("endpoint_error_m", 1.) <= self.config.endpoint_tolerance_m}
        def predict(text):
            observation = dict(self.p._last_obs)
            observation["task_descriptions"] = text
            observation.setdefault("extra_view_images", None)
            return self.p.model.predict(observation, options={"mode": "eval"})
        def step(action):
            self.gripper_command = float(action[6])
            before, after = public_control(self.p, action)
            self.vla_trace.append({"before": before, "after": after, "action": np.asarray(action).tolist()})
            return before, after
        def handoff(trace):
            if not trace:
                return {"steps_used": 0, "completed": True}
            return settle_osc_hold(self.p, self.gripper_command, self.config)
        result = run_fallback(prompt=prompt, prepare=prepare, predict=predict, step=step, observe=observe,
            native_done=lambda: self.p.env.terminated, native_stopped=lambda: self.p.env.terminated or self.p.env.truncated,
            handoff=handoff, budget=self.vla_budget)
        if not (self.p.env.terminated or self.p.env.truncated):
            result["post_handoff_measurement"] = observe()
            final_completed = result["post_handoff_measurement"]["completed"]
            if result['outcome'] == 'success' and not final_completed:
                result.update(outcome='failure', stop_reason='completion_lost_during_handoff')
            if final_completed:
                if mode == "pick":
                    self.held = self.active = source.id
                elif mode in {"on", "in"}:
                    self.held = self.active = None
            elif mode == 'pick':
                self.held = None
        result["template"] = {"version": "measured-libero-subtask/2-selected-instance", "mode": mode, "prompt": prompt}
        result['payload_reference_capture_step'] = (vla_payload_reference['capture_step']
            if vla_payload_reference is not None else None)
        result['payload_reference_artifacts'] = (vla_payload_reference.get('artifacts')
            if vla_payload_reference is not None else None)
        return result
