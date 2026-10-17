"""Measured LIBERO adapter for the shared bounded-skills contract.

No BDDL, oracle RPC or simulator object poses are read here. Candidate geometry
comes from dual-view RGB-D and public robot sensors. Category-specific logic
is confined to the existing grasp-region perception code.
"""
from __future__ import annotations

import copy
import hashlib
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
    public_control,
)
from robots.libero.bounded_screen import PublicRouteScreen
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
    complete_instance_boundary,
    complete_planar_boundary,
    depth_components,
)
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from robots.libero.v5_grasp_route import separate_target_points
from robots.libero.v5_state import fixture_actions
from robots.libero.v5_subtasks import measured_instance_description, subtask_phrase
from rpent.skill_package import VERSION
from rpent.skill_package.contract import (
    FailureMemory,
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
                 record_public_geometry: bool = False):
        self.ex, self.p, self.scene = executor, executor.p, executor.scene
        self.xml = Path(gripper_xml)
        self.geometry = panda_geometry(self.xml)
        if self.xml.is_file():
            self.geometry = {**self.geometry, 'visual_boxes': gripper_visual_boxes(str(self.xml))}
        self.robot_xml = self.xml.parent.parent/"robots/panda/robot.xml"
        self.allow_vla, self.history = allow_vla, history or DevelopmentHistory()
        self.config = motion_config
        self.memory = FailureMemory()
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
        self.latest_request: dict | None = None
        self.preparation = measured_robot(self.p)
        self.gripper_command = -1. if self.preparation["gripper_opening_m"] >= .075 else 1.
        self.previous_scene = {}
        self._base_geometry = None
        self._screen_cache = {}
        self._instance_cache = {}
        self.instance_boundary_evidence = {}
        self._proprio_sample = None
        self.record_public_geometry = record_public_geometry
        self.public_geometry_evidence = {}
        self._last_free_chunk = None
        self.last_prefetch_adoption = None

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

    def refresh(self):
        self.ex.capture()
        self.scene.refresh(sorted(self.scene.vocabulary))
        self._base_geometry = None
        self._screen_cache.clear()
        self._instance_cache.clear()
        self.instance_boundary_evidence.clear()
        self.public_geometry_evidence.clear()
        # Requests publish a self-filtered held surface. Compare the same
        # measurement after capture; a raw SAM centre can differ by centimetres
        # even when neither the object nor the camera moved.
        self._refresh_held_measurement()
        current = {e.id: np.array(e.xyz) for e in self.scene.entities.values() if e.visible}
        changed = any(key not in self.previous_scene or np.linalg.norm(value-self.previous_scene[key]) > .01
                      for key, value in current.items())
        self.memory.tick(scene_changed=changed)
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
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot['eef_quat_xyzw']})
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

        flat = world.reshape(-1, 3)
        ids = np.flatnonzero(np.isfinite(flat).all(axis=1))
        current = cKDTree(self._base_geometry[0]).query(flat[ids],
            distance_upper_bound=np.nextafter(1e-6, np.inf))[0] <= 1e-6
        filtered = np.full_like(flat, np.nan)
        filtered[ids[current]] = flat[ids[current]]
        return filtered.reshape(world.shape)

    def _handle_pixels(self, measurement):
        """Load only the current public handle samples, never a pose prior."""
        if (not measurement or measurement.get('source_step') is None
                or measurement['source_step'] != self.ex.toolkit._state.latest_step):
            return np.empty((0, 3))
        return self._stored_handle_pixels(measurement)

    @staticmethod
    def _stored_handle_pixels(measurement):
        clouds = []
        for view in measurement.get('views', {}).values():
            info = view.get('cloud')
            if (view.get('pose') and info and info.get('source') == 'perception'
                    and info.get('source_step') == measurement['source_step']):
                with np.load(info['path']) as stored:
                    clouds.append(np.asarray(stored[stored.files[0]]).reshape(-1, 3))
        return np.concatenate(clouds) if clouds else np.empty((0, 3))

    def _contact_pixels(self, anchor_id):
        pixels = self._instance_pixels(anchor_id)
        plan = self.plans.get(anchor_id, self.committed_grasps.get(anchor_id, {}).get('plan', {}))
        surface = plan.get('surface_measurement')
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
            current = self._handle_pixels(measured)
            committed = self.committed_grasps.get(anchor_id, {})
            reference = committed.get('contact_robot')
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
                    mask, evidence = complete_contact_surface(world, self._stored_handle_pixels(measured))
                    recovered.append(world[mask])
                    self.instance_boundary_evidence.setdefault(anchor_id, []).append({
                        'camera': camera, 'source': 'current_rgbd_matches_committed_precontact_handle',
                        'reference_capture_step': measured['source_step'],
                        'capture_step': self.ex.toolkit._state.latest_step, **evidence})
                current = np.concatenate(recovered)
            if (not len(current) and reference is not None and self.active == anchor_id
                    and measured_robot(self.p)['gripper_opening_m'] < .075):
                # Only CURRENT pixels within 1 mm of the last measured
                # handle surface can regain contact membership. The stored
                # cloud itself is never subtracted from current obstacles.
                # Use public EEF displacement to track a contacted handle;
                # unrelated adjacent/depth-discontinuous surfaces stay out.
                old = self._stored_handle_pixels(measured)
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
                        normal = measured.get('pose', {}).get('approach_normal_xyz')
                        if (not registration.get('accepted') and normal is not None
                                and registration.get('reason') == 'surface_shift_exceeds_public_hold_tolerance'):
                            # An unconstrained fit can slide along an occluded
                            # handle. Refit only its independently measured
                            # normal, retaining the same displacement gates.
                            normal = rotation@old_rotation.T@np.asarray(normal)
                            predicted, normal_fit = contact_normal_registration(predicted, local, normal)
                            registration = {**normal_fit, 'rigid_fit': registration}
                    recovered, records = [], []
                    for camera in ('agentview', 'wrist'):
                        world = np.asarray(self.ex.toolkit._state.load(camera+'_world_high.npz'))
                        world = self._self_filtered_world(world)
                        extended, boundary = complete_contact_surface(world, predicted, current_boundary=True)
                        recovered.append(world[extended])
                        records.append({'camera': camera, 'source': 'current_rgbd_matches_contacted_handle_surface',
                            'reference_capture_step': measured['source_step'],
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
                        for camera in ('agentview', 'wrist'):
                            world = self._self_filtered_world(np.asarray(
                                self.ex.toolkit._state.load(camera+'_world_high.npz')))
                            flat = world.reshape(-1, 3)
                            valid = np.isfinite(flat).all(axis=1)
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
                    self.instance_boundary_evidence.setdefault(anchor_id, []).extend(records)
            pixels = np.concatenate([pixels, current])
        return pixels

    def _instance_pixels(self, anchor_id):
        # Fusion stores voxel CENTROIDS. They are geometry estimates, not
        # original depth pixels; exact pixel-identity subtraction using them
        # leaves the object itself in the obstacle cloud. Use preserved
        # per-camera samples to remove only measured instance members.
        if anchor_id in self._instance_cache:
            return self._instance_cache[anchor_id]
        views = getattr(self.scene, 'measurement_clouds_by_view', {}).get(anchor_id, {})
        samples, records, current_views = {}, [], {}
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
                    'local_plane': planar, 'connected_surface': connected, **evidence})
                points = world[expanded]
                current_views[camera] = world, expanded
            samples[camera] = points
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
                samples[camera] = world[completed]
                next(row for row in records if row['camera'] == camera)['crossview'] = evidence
        entity = self.scene.entities.get(anchor_id)
        if entity is not None and entity.part_of and samples:
            # The independent fixture band may be segmented in only one
            # view. Recover current pixels of that measured surface in the
            # other view, never pixels inferred from the part's bounds alone.
            current_samples = [points for camera, points in samples.items()
                if views[camera].get('source_step') == self.ex.toolkit._state.latest_step]
            if current_samples:
                surface = np.concatenate(current_samples)
                for camera in ('agentview', 'wrist'):
                    if camera in samples:
                        continue
                    world = np.asarray(self.ex.toolkit._state.load(camera+'_world_high.npz'))
                    completed, evidence = complete_contact_surface(world, surface)
                    crossviews = []
                    for other, (other_world, other_mask) in current_views.items():
                        metadata = self.ex.toolkit._state.load(other+'_metadata.json')
                        completed, crossview = complete_crossview_boundary(world, completed,
                            other_world, other_mask, metadata)
                        crossviews.append({'camera': other, **crossview})
                    samples[camera] = world[completed]
                    records.append({'camera': camera, 'source_step': self.ex.toolkit._state.latest_step,
                        'source': 'current_rgbd_matches_current_measured_fixture_band',
                        'crossviews': crossviews, **evidence})
        if samples:
            result = np.concatenate(list(samples.values()))
        elif anchor_id == self.held and self.payload_reference is not None:
            result = np.empty((0, 3))
        else:
            result = self.scene.measurement_clouds.get(anchor_id, np.empty((0, 3)))
        if anchor_id == self.held and self.payload_reference is not None and self._base_geometry is not None:
            from scipy.spatial import cKDTree

            from robots.libero.bounded_payload import (
                complete_moving_boundary,
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
            member, temporal = moving_payload_pixels(scene, self.payload_reference, measured_robot(self.p),
                                                     current_target=result[present])
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
                    rgb=self.ex.toolkit._state.load(camera+'_high.png'))
                result = np.concatenate([result, world[completed & ~mask]])
                records.append({'camera': camera, **evidence})
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
        _, records = sample_unified_grasps(points, np.empty((0, 3)), entity.name,
            robot['eef_xyz_m'], robot['eef_quat_xyzw'], self.geometry, None,
            robot['eef_xyz_m'][2], candidate_only=True)
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
            'label': entity.name, 'selected': chosen['id'] if chosen else None, 'candidates': records})
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
            parent = self.scene.entities.get(entity.part_of)
            outward = centre-np.asarray(parent.xyz) if parent is not None else np.asarray(robot['eef_xyz_m'])-centre
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
            for yaw in range(0, 360, 45):
                closing = Rotation.from_rotvec(normal*math.radians(yaw)).apply(right)
                site = side_site_rotation(closing, -normal)
                orientation = Rotation.from_matrix(site@Rotation.from_euler('z', math.pi/2).as_matrix())
                # Parallel fingers admit both wrist orientations. The shorter
                # rotation can reach a joint limit while its symmetric pose has
                # a continuous IK route, so screen both instead of pruning one.
                xyz = patch-site@tip
                entry = xyz+normal*.12
                height = max(robot['eef_xyz_m'][2], entry[2])+.08
                over = [{'xyz_m': [*robot['eef_xyz_m'][:2], height], 'quat_xyzw': robot['eef_quat_xyzw']},
                    {'xyz_m': [*entry[:2], height], 'quat_xyzw': orientation.as_quat().tolist()},
                    {'xyz_m': entry.tolist(), 'quat_xyzw': orientation.as_quat().tolist()},
                    {'xyz_m': xyz.tolist(), 'quat_xyzw': orientation.as_quat().tolist()}]
                routes = [('over', over)] if horizontal else [('direct', over[-2:]), ('over', over)]
                for path, route in routes:
                    choices.append({'patch_index': patch_index, 'contact_xyz_m': patch.tolist(),
                        'yaw_deg': yaw, 'path': path, 'xyz_m': xyz.tolist(),
                        'quat_xyzw': orientation.as_quat().tolist(), 'approach_xyz_m': entry.tolist(), 'route': route,
                        'wrist_change_rad': float((orientation*current.inv()).magnitude()), 'screen': None})
        choices.sort(key=lambda item: (item['patch_index'], item['wrist_change_rad'], item['yaw_deg']))
        selected = None
        screen = self._cloud_and_ik(entity.id, contact=True)
        for option in choices:
            if selected is not None:
                break
            from robots.libero.v5_geometric_grasp import collision_counts
            site = Rotation.from_quat(option['quat_xyzw']).as_matrix()@Rotation.from_euler('z', -math.pi/2).as_matrix()
            for opening in np.linspace(.08, 0., 9):
                external = collision_counts(screen.points, option['xyz_m'], site, self.geometry, opening, clearance_m=.004)
                own = collision_counts(screen.target, option['xyz_m'], site, self.geometry, opening, clearance_m=.004)
                if any(external.values()) or own.get('palm', 0):
                    option['closure'] = {'opening_m': float(opening), 'scene': external, 'target': own}
                    break
            if option.get('closure'):
                continue
            _, _, _, evidence = SmoothMotion(self.p, screen, self.config).prepare(option['route'])
            option['screen'] = {k: evidence[k] for k in ('passed', 'reason', 'collision', 'ik_reachable', 'path_min_clearance_m')}
            if evidence['passed']:
                selected = option
        self.candidate_diagnostics.append({'stage': 'measured_surface_contact', 'anchor_id': entity.id,
            'source': 'fused_rgbd_shape_and_static_finger_tip_geometry',
            'contact_xyz_m': selected['contact_xyz_m'] if selected else None,
            'contact_patches_xyz_m': [patch.tolist() for patch in contacts], 'measured_extent_m': extent.tolist(),
            'surface_normal_xyz': normal.tolist(),
            'grasp_verified': False, 'candidates': choices,
            'selected_yaw_deg': selected['yaw_deg'] if selected else None})
        if selected is None:
            return None
        right_axis, front = map(np.asarray, self.scene.view_axes)
        directions = {'above': np.array([0., 0., 1.]), 'front': front,
                      'left': -right_axis, 'right': right_axis}
        return {k: selected[k] for k in ('xyz_m', 'quat_xyzw', 'approach_xyz_m')} | {
            'approach_route': selected['route'][:-1],
            'preferred_approach': max(directions, key=lambda key: np.dot(normal, directions[key])),
            'preferred_path': selected['path'],
            'width_m': None, 'contact_kind': 'surface',
            'surface_measurement': {'xyz_world': self._instance_pixels(entity.id).tolist(),
                'source_step': entity.source_step, 'normal_xyz': normal.tolist()}}

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
                if len(handle_points) >= 10:
                    closing = (orientation*Rotation.from_euler('z', -math.pi/2)).as_matrix()[:, 0]
                    extent = np.quantile(handle_points@closing, [.02, .98])
                    width = float(extent[1]-extent[0])
                orientations.append((orientation, roll, width))
        choices = []
        for orientation, roll, width in orientations:
            quat = orientation.as_quat().tolist()
            for distance in (.12, .08, .04):
                entry = contact+normal*distance
                height = max(robot['eef_xyz_m'][2], entry[2])+.08
                high_start = [*robot['eef_xyz_m'][:2], height]
                high_entry = [*entry[:2], height]
                for rotate_at in ('entry', 'clearance'):
                    route = [
                        {'xyz_m': high_start, 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': high_entry, 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': entry.tolist(), 'quat_xyzw': robot['eef_quat_xyzw']},
                        {'xyz_m': entry.tolist(), 'quat_xyzw': quat}]
                    if rotate_at == 'clearance':
                        route = [route[0], {'xyz_m': high_start, 'quat_xyzw': quat},
                            {'xyz_m': high_entry, 'quat_xyzw': quat}, route[-1]]
                    route.append({'xyz_m': contact.tolist(), 'quat_xyzw': quat})
                    choices.append({'stand_off_m': distance, 'rotate_at': rotate_at,
                        'handle_roll_deg': roll, 'width_m': width, 'route': route, 'screen': None})
        screen = self._cloud_and_ik(entity.id, contact=True)
        selected = None
        for index, option in enumerate(choices):
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
                selected = index
                break
        self.candidate_diagnostics.append({'stage': 'fixture_route_search',
            'anchor_id': entity.id, 'source': 'measured_handle_and_static_gripper_geometry',
            'selected': selected, 'candidates': choices})
        if selected is None:
            return None
        route = choices[selected]['route']
        return {**plan, 'quat_xyzw': route[-1]['quat_xyzw'],
            'width_m': choices[selected]['width_m'],
            'approach_xyz_m': route[-2]['xyz_m'], 'approach_route': route[:-1]}

    def _route(self, skill, parameters, *, robot=None):
        robot = robot or measured_robot(self.p)
        start = np.array(robot["eef_xyz_m"])
        quat = robot["eef_quat_xyzw"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        entity = self.scene.entities.get(key)
        if self.held is not None and key != self.held and key in self.target_cache:
            entity = self.target_cache[key]
        elif entity is None or not entity.visible:
            entity = self.target_cache.get(key)
        point = start.copy()
        if skill in {"move_to", "align", "descend"}:
            contact = self.plans.get(key)
            if contact is None:
                return None
            goal = np.array(contact["xyz_m"])
            approach = parameters.get("approach", "above")
            right, front = map(np.asarray, self.scene.view_axes)
            direction = {"above": np.array([0., 0., 1.]), "front": front,
                         "left": -right, "right": right}[approach]
            if skill == "align":
                return [{"xyz_m": start.tolist(), "quat_xyzw": contact["quat_xyzw"]}]
            if skill == "descend":
                return [{"xyz_m": goal.tolist(), "quat_xyzw": contact["quat_xyzw"]}]
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
            offset = start-np.asarray(held.xyz)
            point = np.asarray(entity.xyz)+offset
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
                return None
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
                "history": history, "recent_failures": 0, "last_failure": None}

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
                        continue
                    self.plans[entity.id] = screened
                    self.candidate_diagnostics.append({'stage': 'fixture_contact_plan',
                        'anchor_id': entity.id, 'label': entity.name, 'plan': copy.deepcopy(self.plans[entity.id])})
            elif not entity.part_of and not entity.name.startswith("area ") and not entity.name.endswith("surface"):
                contact = self.grasp_geometry(entity)
                if contact is not None:
                    self.plans[entity.id] = contact
        candidates = []
        def add(skill, **parameters):
            candidate = self._candidate(skill, parameters, screen_options=screen_options)
            if candidate is not None:
                candidates.append(candidate)
        for entity in entities:
            if entity.id in self.plans and self.held is None:
                for approach in ("above", "front", "left", "right"):
                    for path in ("direct", "over", "around"):
                        add("move_to", anchor_id=entity.id, approach=approach, path=path)
                for skill in ("align", "descend", "lift"):
                    add(skill, anchor_id=entity.id)
            if self.held and entity.id != self.held:
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
        from robots.libero.v5_state import relations
        right, front = self.scene.view_axes
        public_relations = []
        relation_entities = [self.target_cache.get(e.id, e)
            if (self.held is not None and e.id != self.held)
                or (not e.visible and self._has_anchor(e)) else e for e in self.scene.entities.values()]
        for row in relations(relation_entities, right_axis=right, front_axis=front):
            _, source, relation, target = row.split()
            public_relations.append({"source_id": source, "relation": relation, "target_id": target})
        request = {"schema_version": VERSION, "kind": "request", "observation_id": f"public-{self.revision}",
            "revision": self.revision, "instruction": self.ex.instruction,
            "remaining_sim_steps": self.p.env.execution_budget()["remaining_sim_steps"],
            "anchors": self.anchors(), "robot": self.robot(), "candidates": self.memory.apply(candidates),
            "receipts": self.receipts[-3:], "relations": public_relations, "max_actions": k}
        validate(request)
        self.latest_request = request
        return request

    def snapshot_decision_context(self):
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
        template["robot"] = clone.robot()
        template["remaining_sim_steps"] = budget["remaining_sim_steps"]
        template["revision"] = self.revision+1
        template["observation_id"] = f"prefetch-{self.revision+1}-step{budget['used_sim_steps']}"
        def build_request():
            request = copy.deepcopy(template)
            request["candidates"] = [candidate for c in template["candidates"]
                if (candidate := clone._candidate(c["skill"], c["parameters"])) is not None]
            request["candidates"] = clone.memory.apply(request["candidates"])
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
        if not exact:
            chunk = self._last_free_chunk
            # A moving prefetch necessarily predates the endpoint's robot,
            # budget and successful motion receipts. It remains an honest
            # earlier observation: do not relabel those measurements as new.
            # Only the just-completed free-motion chunk may bridge that age;
            # contact/failure cannot be predicted by a pre-contact request.
            if (decision is None or chunk is None or chunk['revision']+1 != self.revision
                    or request['receipts'] != chunk['parent_receipts']
                    or not (self.p.env.execution_budget()['remaining_sim_steps']
                        <= request['remaining_sim_steps'] <= chunk['remaining_sim_steps'])
                    or chunk['end_robot'] != self.robot()):
                return False
        if self.receipts and self.receipts[-1]["outcome"] != "success":
            return False
        for anchor in request["anchors"]:
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

    def execute(self, request, decision, *, async_decisions=None):
        choices = selected(request, decision)
        if self.latest_request is not request:
            raise ValueError("request is not the adapter's current observation")
        free_chunk = all(c['skill'] in MOTION_SKILLS and not is_boundary(c) for c in choices)
        parent_receipts = copy.deepcopy(self.receipts[-3:])
        remaining_at_start = self.p.env.execution_budget()['remaining_sim_steps']
        # Each suffix is resolved from current public geometry; a contact or
        # newly measured scene change ends the chunk before any stale suffix.
        outcomes = []
        # Contact outcomes cannot be predicted by a pre-contact request.
        lookahead = async_decisions if not any(is_boundary(c) for c in choices) else None
        prefix = []
        for candidate in choices:
            if is_boundary(candidate) or candidate["skill"] not in MOTION_SKILLS:
                break
            prefix.append(candidate)
        if len(prefix) > 1:
            outcomes.extend(self._execute_motion_group(request, prefix, lookahead=lookahead))
            choices = choices[len(prefix):] if all(r["outcome"] == "success" for r in outcomes) else []
        for candidate in choices:
            receipt = self._execute_one(request, candidate, lookahead=lookahead)
            outcomes.append(receipt)
            self.receipts.append(receipt)
            self.memory.record(candidate, receipt["outcome"], receipt["stop_reason"])
            if receipt["outcome"] != "success" or candidate["skill"] not in MOTION_SKILLS:
                break
        self.revision += 1
        self._last_free_chunk = ({'revision': request['revision'], 'parent_receipts': parent_receipts,
            'remaining_sim_steps': remaining_at_start, 'end_robot': self.robot()}
            if free_chunk and outcomes and all(r['outcome'] == 'success' for r in outcomes) else None)
        return outcomes

    def _execute_motion_group(self, request, candidates, *, lookahead=None):
        """Blend adjacent free motions; report each waypoint's measured passage."""
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
        motion = SmoothMotion(self.p, self._cloud_and_ik(), self.config)
        result = motion.run(waypoints, gripper=self.gripper_command, blend=True,
            lookahead=lookahead, request_factory=self.snapshot_decision_context if lookahead is not None else None)
        self.refresh()
        trace = result.get("trace", [])
        cursor, receipts = 0, []
        for candidate, boundary in zip(candidates, boundaries):
            target = np.asarray(waypoints[boundary]["xyz_m"])
            # Desired passage partitions the executed stream. It is not an
            # extra servo stop, nor a claim the actual pose hit the waypoint.
            if trace:
                candidates_i = range(cursor, len(trace))
                passage_time = result['waypoint_times_s'][boundary]
                at = min(candidates_i, key=lambda i: abs(trace[i]['time_s']-passage_time)) if cursor < len(trace) else len(trace)-1
                segment = trace[cursor:at+1]
                after_raw = trace[at]["after"]
                before_raw = segment[0]["before"] if segment else after_raw
                error = float(np.linalg.norm(np.asarray(after_raw["eef_xyz_m"])-target))
                angular_error = float((Rotation.from_quat(after_raw['eef_quat_xyzw'])*
                    Rotation.from_quat(waypoints[boundary]['quat_xyzw']).inv()).magnitude())
                cursor = at+1
                def sensor(raw):
                    return {k: raw[k] for k in ("eef_xyz_m", "eef_quat_xyzw", "gripper_opening_m")} | {
                        "held_anchor_id": self.held, "velocity_m_s": None}
                before, after = sensor(before_raw), sensor(after_raw)
            else:
                segment, error, angular_error, before, after = [], float("inf"), float('inf'), request["robot"], self.robot()
            outcome = "success" if error <= self.config.endpoint_tolerance_m and angular_error <= .05 else "failure"
            reason = "measured_waypoint_passage" if outcome == "success" else (
                'angular_waypoint_not_reached' if error <= self.config.endpoint_tolerance_m else result["stop_reason"])
            receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
                "candidate_id": candidate["id"], "skill": candidate["skill"], "outcome": outcome,
                "phase": None if outcome == "success" else "planning_unreachable", "stop_reason": reason,
                "steps_used": len(segment), "before": before, "after": after, "changes": [],
                "evidence": [self._evidence(e) for e in self.scene.entities.values()]}
            validate(receipt)
            receipts.append(receipt)
            self.receipts.append(receipt)
            self.memory.record(candidate, outcome, reason)
        self.details.append({"candidate_ids": [c["id"] for c in candidates], "execution": result,
                             "blended": True, "waypoint_errors_are_measured": True})
        return receipts

    def _execute_one(self, request, candidate, *, lookahead=None):
        before = self.robot()
        start_steps = self.p.env.execution_budget()["used_sim_steps"]
        entities_before = dict(self.scene.entities)
        observed_before = self.previous_scene | {
            eid: np.asarray(entity.xyz) for eid, entity in entities_before.items() if entity.visible}
        skill, parameters = candidate["skill"], candidate["parameters"]
        key = parameters.get("anchor_id", parameters.get("target_id"))
        phase, outcome, reason, detail = None, "unmeasured", "measurement_missing", {}
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
                    request_factory=self.snapshot_decision_context if lookahead is not None else None)
                reason = detail["stop_reason"]
                angular_error = (Rotation.from_quat(route[-1]["quat_xyzw"])*Rotation.from_quat(self.robot()["eef_quat_xyzw"]).inv()).magnitude()
                detail["angular_endpoint_error_rad"] = float(angular_error)
                outcome = "success" if (detail.get("endpoint_error_m", 1.) <= self.config.endpoint_tolerance_m
                    and angular_error <= .05 and detail["stop_reason"] in {"endpoint", "native_stop", "decision_pending_at_rest_endpoint"}) else "failure"
                phase = None if outcome == "success" else ("collision" if "collision" in reason else "planning_unreachable")
                if skill == 'descend' and outcome == 'success':
                    self.active = key
                if outcome != 'success':
                    self.committed_grasps.pop(key, None)
        elif skill in {"release", "set_gripper"}:
            opening = skill == "release" or parameters.get("mode") == "open"
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
                point = np.array(before["eef_xyz_m"])+[0., 0., .04]
                detail = SmoothMotion(self.p, self._cloud_and_ik(self.active, contact=self.active is not None), self.config).run([{"xyz_m": point.tolist()}], gripper=self.gripper_command)
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
        self.refresh()
        if skill == 'observe':
            self.committed_grasps.clear()
            if (parameters['mode'] == 'wrist_scan' and self.held is None
                    and np.linalg.norm(np.asarray(self.robot()['eef_xyz_m'])-before['eef_xyz_m'])
                    > self.config.endpoint_tolerance_m):
                # A measured scan withdrawal breaks unverified surface
                # contact. Do not let the next nudge act on its old identity
                # while the hand is now above the object.
                self.active = None
                self.grasp_reference = None
        if skill == 'set_gripper' and parameters.get('mode') == 'close' and self.active:
            if self.active in self.committed_grasps:
                self.committed_grasps[self.active]['contact_robot'] = measured_robot(self.p)
            contact_entity = self.scene.entities.get(self.active)
            # Closing can move an object and change its visible surface.
            # Test subsequent lift coupling against the post-close sample,
            # never against an image captured before descent/contact.
            self.grasp_reference = (copy.deepcopy(contact_entity), np.array(self.robot()['eef_xyz_m'])) if contact_entity and contact_entity.visible else None
        if skill == "observe" and outcome == "success":
            # Moving the camera alone cannot reset recovery failures. A scan
            # must reveal an entity or a measured scene change; otherwise
            # repeated upward scans can consume the entire episode.
            changed = any(eid not in observed_before
                or np.linalg.norm(np.asarray(entity.xyz)-observed_before[eid]) >= .01
                for eid, entity in self.scene.entities.items() if entity.visible)
            if not changed:
                outcome, reason = "no_effect", "no_measured_scene_change"
        if skill == 'nudge' and key is not None and outcome == 'success':
            prior = entities_before.get(key)
            current = self.scene.entities.get(key)
            measured = (prior is not None and prior.visible and current is not None
                and current.visible and current.source_step > prior.source_step)
            displacement = np.asarray(current.xyz)-prior.xyz if measured else None
            detail['public_contact_motion'] = {
                'source': 'paired_public_rgbd_entity_measurements',
                'before_capture_step': prior.source_step if prior is not None else None,
                'after_capture_step': current.source_step if current is not None else None,
                'displacement_m': displacement.tolist() if measured else None,
                'minimum_progress_m': .005}
            # EEF arrival alone says nothing about a contacted object moving.
            # Preserve free-space nudges and the benchmark's native success.
            if not self.p.env.terminated:
                if not measured:
                    outcome, phase, reason = 'unmeasured', 'verification_error', 'contact_motion_unmeasured'
                elif np.linalg.norm(displacement) < .005:
                    outcome, phase, reason = 'no_effect', 'contact_failure', 'contact_no_measured_progress'
        if skill == "lift" and self.grasp_reference is not None:
            source, eef_at_contact = self.grasp_reference
            current = self.scene.entities.get(key)
            if source is not None and current is not None and current.visible:
                rise = current.lower[2]-source.lower[2]
                coupling = np.linalg.norm((np.array(current.xyz)-source.xyz)-(np.array(self.robot()["eef_xyz_m"])-eef_at_contact))
                opening = self.robot()["gripper_opening_m"]
                aperture, aperture_evidence = self.holding_aperture(opening)
                detail["public_hold"] = {"rise_m": rise, "relative_displacement_m": float(coupling),
                                         "opening_m": opening, 'aperture': aperture_evidence}
                if rise >= .03 and coupling <= .015 and aperture:
                    self.held = key
                    if payload_reference is not None:
                        self.payload_reference = payload_reference
                else:
                    outcome, phase, reason = "failure", "contact_failure", "public_hold_not_verified"
            else:
                outcome, phase, reason = "unmeasured", "verification_error", "lifted_object_not_visible"
        changes = [{"anchor_id": eid,
            "displacement_m": (np.asarray(entity.xyz)-entities_before[eid].xyz).tolist() if eid in entities_before and entity.visible else None,
            "held": eid == self.held if self.held else None, "relation": None, "fixture_state": None}
            for eid, entity in self.scene.entities.items()]
        receipt = {"schema_version": VERSION, "kind": "receipt", "observation_id": request["observation_id"],
            "candidate_id": candidate["id"], "skill": skill, "outcome": outcome, "phase": phase,
            "stop_reason": reason, "steps_used": self.p.env.execution_budget()["used_sim_steps"]-start_steps,
            "before": before, "after": self.robot(), "changes": changes,
            "evidence": [self._evidence(entity) for entity in self.scene.entities.values()]}
        validate(receipt)
        self.details.append({"candidate_id": candidate["id"], "execution": detail})
        self.ex.held = self.held
        return receipt

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
            plan = copy.deepcopy(self.plans[key])
            plan['contact_evidence'] = self._evidence(entity)
            self.plans[key] = plan
            self.committed_grasps[key] = {'plan': plan, 'anchor_xyz': np.array(entity.xyz)}

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
                return {"steps_used": 0}
            motion = SmoothMotion(self.p, self._cloud_and_ik(source.id, contact=True), self.config)
            rows = [{"time_s": i/self.config.hz, "before": row["before"], "after": row["after"]}
                    for i, row in enumerate(trace[-4:])]
            braking = motion._brake(rows, self.gripper_command)
            return {**braking, "trace": rows,
                "public_geometry_evidence": copy.deepcopy(self.public_geometry_evidence),
                "instance_boundary_evidence": copy.deepcopy(self.instance_boundary_evidence)}
        result = run_fallback(prompt=prompt, prepare=prepare, predict=predict, step=step, observe=observe,
            native_done=lambda: self.p.env.terminated, native_stopped=lambda: self.p.env.terminated or self.p.env.truncated,
            handoff=handoff, budget=VLABudget())
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
