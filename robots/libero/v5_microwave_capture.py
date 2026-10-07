# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Opt-in microwave endpoint captures from current public RGB-D and robot sensors.

This collector reads only explicit artifacts owned by the current state record.
No simulator joint, object pose, task predicate, directory scan or goal is used.
Withdrawing between action blocks changes the controller and remains an opt-in
development experiment; missing withdrawal or mask evidence cannot admit stop.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import math
import time
from pathlib import Path

import numpy as np

from robots.libero.v5_microwave_door_temporal import (
    MicrowaveDoorTemporalConfig, _plane, measure_microwave_capture_pair, measure_microwave_door_temporal,
)
from robots.libero.v5_verification import vertical_face


VERSION = "microwave-public-dual-temporal-capture/1-dev"
CAMERAS = ("agentview", "wrist")
BASELINE_CAPTURE_MAX_PAIRS = 3
OBSERVATION_POSE_VERSION = "microwave-public-plane-observation-pose/1-dev"
READONLY_PROBE_VERSION = "microwave-public-readonly-endpoint-probe/1-dev"


def public_endpoint_candidate(sample, mode):
    """Trigger fresh confirmation from one public fit; never authorize a stop."""
    evidence = {"version": READONLY_PROBE_VERSION, "source": "perception",
                "status": "unmeasured", "endpoint_candidate": False,
                "stop_admitted": False, "trigger_only": True,
                "occluded": sample.get("occluded"), "arm_withdrawn": sample.get("arm_withdrawn")}
    if (mode not in ("open", "close") or sample.get("source") != "perception"
            or sample.get("frame_id") != "world" or sample.get("length_unit") != "m"
            or type(sample.get("source_step")) is not int):
        return {**evidence, "reason": "current_public_world_measurement_missing"}
    config = MicrowaveDoorTemporalConfig()
    overlap = sample.get("frame_moving_mask_overlap")
    if overlap is None or not np.isfinite(overlap) or not 0 <= overlap <= config.maximum_mask_overlap:
        return {**evidence, "reason": "independent_frame_and_door_masks_not_measured"}
    planes = {}
    for kind in ("frame", "moving"):
        record = sample.get(kind)
        if not isinstance(record, dict) or record.get("mask_count") != 1:
            return {**evidence, "reason": kind + "_plane_missing_or_ambiguous"}
        plane, reason = _plane(record, sample, config)
        if reason:
            return {**evidence, "reason": kind + "_" + reason}
        planes[kind] = plane
    if any(key in planes["frame"] and planes["frame"][key] == planes["moving"].get(key)
           for key in ("path", "sha256", "mask_id")):
        return {**evidence, "reason": "frame_and_door_share_same_measurement"}
    angle = math.degrees(math.acos(float(np.clip(abs(np.asarray(planes["frame"]["normal_xy"])
                                                   @ planes["moving"]["normal_xy"]), 0., 1.))))
    candidate = angle >= config.open_minimum_angle_deg if mode == "open" else angle <= config.close_maximum_angle_deg
    return {**evidence, "status": "measured", "reason": "endpoint_candidate" if candidate else "non_endpoint",
            "endpoint_candidate": bool(candidate), "relative_angle_deg": angle, "measured_planes": planes}


def points_mask(world, cloud):
    """Locate explicitly measured cloud points in their original RGB-D map."""
    world = np.asarray(world)
    flat = np.ascontiguousarray(world.reshape(-1, 3), dtype=np.float64)
    selected = np.ascontiguousarray(cloud, dtype=np.float64).reshape(-1, 3)
    row_type = np.dtype((np.void, flat.dtype.itemsize * 3))
    return np.isin(flat.view(row_type).ravel(), selected.view(row_type).ravel()).reshape(world.shape[:2])


def _identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _load_cloud(record):
    with np.load(record["path"], allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError("measurement cloud requires one explicit array")
        return np.asarray(saved[saved.files[0]])


def _public_robot_clearance(eef, parent, minimum=.12):
    eef = np.asarray(eef, dtype=float)
    lo, hi = np.asarray(parent.lower), np.asarray(parent.upper)
    distance = float(np.linalg.norm(np.maximum(0., np.maximum(lo - eef, eef - hi))))
    return {"source": "robot_proprioception_and_measured_fixture_bounds",
            "eef_xyz_m": eef.tolist(), "distance_to_fixture_bounds_m": distance,
            "minimum_distance_m": minimum, "clear": bool(np.isfinite(eef).all() and distance >= minimum)}


def combine_public_planes(views, state, parent):
    """Fuse unique measured per-view planes while retaining independence evidence."""
    sample = {"source": "perception", "frame_id": "world", "length_unit": "m",
              "source_step": state.latest_step, "source_cameras": [], "views": views,
              "fusion_version": "rgbd_dual_view/1", "frame": None, "moving": None,
              "frame_moving_mask_overlap": None, "measurement_counts": {}}
    overlaps = []
    for camera, view in views.items():
        if view.get("frame") and view.get("moving"):
            overlap = view.get("frame_moving_mask_overlap")
            if overlap is not None:
                overlaps.append(float(overlap))
    sample["frame_moving_mask_overlap"] = max(overlaps) if overlaps else None
    for kind in ("frame", "moving"):
        measured = [(camera, view[kind]) for camera, view in views.items() if view.get(kind)]
        # A mask ambiguity in one contributing view cannot become a unique fused mask.
        measured = [(camera, record) for camera, record in measured
                    if record.get("mask_count") == 1 and record.get("source_step") == state.latest_step]
        sample["measurement_counts"][kind] = {"accepted_views": [camera for camera, _ in measured]}
        if not measured:
            continue
        # A camera which sees a different plane must not contaminate the join.
        if len(measured) == 2:
            normal = np.asarray(measured[0][1]["normal_xy"])
            other = np.asarray(measured[1][1]["normal_xy"])
            gap = abs(float((np.asarray(measured[0][1]["centre"][:2])
                             - measured[1][1]["centre"][:2]) @ normal))
            if abs(float(normal @ other)) < math.cos(math.radians(10)) or gap > .015:
                sample["measurement_counts"][kind]["reason"] = "dual_views_disagree"
                continue
        clouds = [_load_cloud(record) for _, record in measured]
        cloud = np.concatenate(clouds)
        fit = vertical_face(cloud)
        if fit is None:
            sample["measurement_counts"][kind]["reason"] = "fused_plane_not_measured"
            continue
        digest = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
        filename = f"microwave_temporal_{parent.id}_{kind}_{digest}.npz"
        if state.save(filename, cloud, step=state.latest_step) is None:
            raise RuntimeError("could not persist current public microwave cloud")
        identity = _identity(state.artifact_path(filename, step=state.latest_step))
        sample[kind] = {**fit, **identity, "source": "perception", "frame_id": "world",
                        "length_unit": "m", "source_step": state.latest_step,
                        "source_cameras": [camera for camera, _ in measured], "mask_count": 1,
                        "mask_id": f"{kind}:{state.latest_step}:{digest}"}
        sample["source_cameras"] = sorted(set(sample["source_cameras"]) | {camera for camera, _ in measured})
    return sample


class MicrowaveEndpointCapture:
    """Capture two fresh unobstructed views per phase and check between blocks."""

    def __init__(self, executor, parent, mode, *, stop_enabled=False, every_chunks=1,
                 interval_s=.3, control_dt_s=.05, observation_pose_enabled=False,
                 readonly_probe_enabled=False):
        if parent.name != "microwave" or mode not in ("open", "close"):
            raise ValueError("microwave capture requires a measured microwave and open/close mode")
        if every_chunks < 1 or interval_s < .3 or control_dt_s <= 0:
            raise ValueError("invalid microwave capture interval")
        self.executor, self.parent, self.mode = executor, parent, mode
        self.stop_enabled, self.every_chunks = bool(stop_enabled), int(every_chunks)
        self.interval_s, self.control_dt_s = float(interval_s), float(control_dt_s)
        self.records, self.before = [], []
        self.observation_pose_enabled = bool(observation_pose_enabled)
        self.observation_height_m = None
        self.readonly_probe_enabled = bool(readonly_probe_enabled)

    def observation_pose(self, sample):
        """Raise, then translate toward two independent current measured planes."""
        ex, p = self.executor, self.executor.p
        current = np.asarray(p._last_obs_eef_pos, dtype=float).copy()
        evidence = {"version": OBSERVATION_POSE_VERSION, "source": "perception_and_robot_proprioception",
                    "source_step": sample.get("source_step"), "initial_eef_xyz_m": current.tolist(),
                    "planning_observation": copy.deepcopy(sample), "moves": [],
                    "status": "unmeasured", "private_truth_used": False}
        if (sample.get("source") != "perception" or sample.get("frame_id") != "world"
                or sample.get("length_unit") != "m"
                or sample.get("source_step") != ex.toolkit._state.latest_step):
            evidence["reason"] = "current_public_world_measurement_missing"
            return evidence
        config = MicrowaveDoorTemporalConfig()
        overlap = sample.get("frame_moving_mask_overlap")
        if overlap is None or not np.isfinite(overlap) or not 0 <= overlap <= config.maximum_mask_overlap:
            evidence["reason"] = "independent_frame_and_door_masks_not_measured"
            return evidence
        planes = {}
        for kind in ("frame", "moving"):
            record = sample.get(kind)
            if not isinstance(record, dict) or record.get("mask_count") != 1:
                evidence["reason"] = kind + "_plane_missing_or_ambiguous"
                return evidence
            plane, reason = _plane(record, sample, config)
            if reason:
                evidence["reason"] = kind + "_" + reason
                return evidence
            planes[kind] = plane
        if any(key in planes["frame"] and planes["frame"][key] == planes["moving"].get(key)
               for key in ("path", "sha256", "mask_id")):
            evidence["reason"] = "frame_and_door_share_same_measurement"
            return evidence
        if not np.isfinite(current).all():
            evidence["reason"] = "current_robot_position_missing"
            return evidence
        midpoint = (np.asarray(planes["frame"]["centre"]) + np.asarray(planes["moving"]["centre"])) / 2
        if self.observation_height_m is None:
            # A fixed public clearance height avoids accumulating 5cm on each
            # baseline retry. After contact, restore it before translation.
            self.observation_height_m = max(float(current[2]) + .05, float(self.parent.upper[2]) + .15)
        high = current.copy()
        high[2] = max(float(current[2]), self.observation_height_m)
        lateral = midpoint[:2] - current[:2]
        length = float(np.linalg.norm(lateral))
        if length > .15:
            lateral *= .15 / length
        translated = high.copy()
        translated[:2] += lateral
        evidence.update(measured_planes=planes, measured_midpoint_xyz_m=midpoint.tolist(),
                        waypoints_xyz_m=[high.tolist(), translated.tolist()],
                        maximum_translation_m=.15, acceptance_distance_m=.03)
        for phase, target in (("raise", high), ("translate", translated)):
            before = np.asarray(p._last_obs_eef_pos, dtype=float).copy()
            move = {"phase": phase, "target_xyz_m": target.tolist(), "before_eef_xyz_m": before.tolist()}
            if p.env.terminated or p.env.truncated:
                evidence.update(status="interrupted", reason="execution_interrupted")
                break
            try:
                move["receipt"] = ex.move(target, -1., tolerance_m=.03, recoverable=True)
            except Exception as error:
                move["error"] = repr(error)
            actual = np.asarray(p._last_obs_eef_pos, dtype=float).copy()
            move.update(actual_eef_xyz_m=actual.tolist(), actual_distance_m=float(np.linalg.norm(actual - target)))
            move["waypoint_reached_by_proprioception"] = bool(np.isfinite(actual).all() and move["actual_distance_m"] <= .03)
            evidence["moves"].append(move)
            if "error" in move or not move["waypoint_reached_by_proprioception"]:
                evidence.update(status="not_reached", reason="measured_observation_waypoint_not_reached")
                break
        else:
            evidence.update(status="reached", reason="measured_observation_waypoints_reached")
        evidence["final_eef_xyz_m"] = np.asarray(p._last_obs_eef_pos, dtype=float).tolist()
        evidence["final_clearance"] = _public_robot_clearance(p._last_obs_eef_pos, self.parent)
        return evidence

    def withdraw(self):
        """Move from contact to measured clearance; report actual achieved pose."""
        ex, p = self.executor, self.executor.p
        evidence = {"version": VERSION, "moves": [], "before":
                    _public_robot_clearance(p._last_obs_eef_pos, self.parent),
                    "gripper_opening_before_m": float(p._last_obs_gripper)}
        # A grip around a fixture must be released before withdrawal to avoid
        # dragging the door away from an endpoint during the measurement.
        if p._last_obs_gripper < .07:
            evidence["release"] = p.release(max_steps=20)
        evidence["gripper_opening_after_m"] = float(p._last_obs_gripper)
        if evidence["gripper_opening_after_m"] < .07:
            evidence["reason"] = "fixture_grip_not_released"
            evidence["after"] = _public_robot_clearance(p._last_obs_eef_pos, self.parent)
            return evidence
        if p.env.terminated or p.env.truncated:
            evidence["reason"] = "execution_interrupted"
            return evidence
        if evidence["before"]["clear"]:
            evidence.update(after=_public_robot_clearance(p._last_obs_eef_pos, self.parent),
                            reason="measured_clearance")
            return evidence
        current = np.asarray(p._last_obs_eef_pos).copy()
        high = current.copy()
        high[2] = max(float(current[2]), float(self.parent.upper[2]) + .15)
        evidence["moves"].append(ex.move(high, -1., tolerance_m=.03, recoverable=True))
        evidence["after"] = _public_robot_clearance(p._last_obs_eef_pos, self.parent)
        # Do not infer withdrawal from the commanded waypoint or move result.
        evidence["reason"] = "measured_clearance" if evidence["after"]["clear"] else "clearance_not_reached"
        return evidence

    def _robot_occlusion(self, camera, measurement):
        """A missing robot mask is unknown, not evidence of an unobstructed view."""
        from rpent.robots.components.sam3_client import Sam3Client

        ex, scene, state = self.executor, self.executor.scene, self.executor.toolkit._state
        image = base64.b64encode(state.load_bytes(f"{camera}_high.png")).decode("ascii")
        world = state.load(f"{camera}_world_high.npz")
        robot_masks = []
        queries = []
        # Job4484 missed the compound prompt in five current frames even
        # though both fixture planes were visible. Query each robot part on
        # that same image before calling it unmeasured; absence never proves
        # clearance. If the compound mask exists, keep the original query.
        for prompt in ("robot arm and gripper", "robot arm", "robot gripper"):
            reply = scene.rpc.call("sam3.segment_all", kwargs={"image_base64": image,
                                   "text_prompt": prompt, "min_score": .35}, timeout_s=120)
            scene.calls += 1
            masks = []
            for item in reply.get("instances", []):
                mask = Sam3Client._decode_result(item).mask
                if mask is not None and mask.shape == world.shape[:2] and mask.any():
                    masks.append(mask)
            queries.append({"prompt": prompt, "valid_masks": len(masks)})
            robot_masks.extend(masks)
            if prompt == "robot arm and gripper" and masks:
                break
        evidence = {"camera": camera, "robot_masks": len(robot_masks), "queries": queries,
                    "occluded": None}
        if not robot_masks or not measurement.get("frame") or not measurement.get("moving"):
            return evidence
        region_masks = []
        for kind in ("frame", "moving"):
            mask_identity = measurement[kind].get("mask_artifact")
            if not mask_identity:
                return evidence
            with np.load(mask_identity["path"], allow_pickle=False) as saved:
                mask = saved["array"]
            if mask.shape != world.shape[:2]:
                return evidence
            region_masks.append(mask.astype(bool))
        robot = np.logical_or.reduce(robot_masks)
        name = f"microwave_temporal_robot_{camera}_mask.npz"
        if state.save(name, robot, step=state.latest_step) is None:
            raise RuntimeError("could not persist current public robot occlusion mask")
        fractions = [float(np.count_nonzero(robot & mask) / max(1, np.count_nonzero(mask))) for mask in region_masks]
        evidence.update(overlap_by_region=dict(zip(("frame", "moving"), fractions)),
                        robot_mask_artifact=_identity(state.artifact_path(name, step=state.latest_step)),
                        occluded=bool(max(fractions) > .02))
        return evidence

    def capture(self, withdrawal):
        ex, scene, state = self.executor, self.executor.scene, self.executor.toolkit._state
        ex.capture(sync_robot=True)
        timestamp = time.monotonic()
        measurement = scene.measure_fixture_endpoint(self.parent, "microwave door", temporal_capture=True)
        views = measurement.get("views")
        if not isinstance(views, dict):
            views = {"agentview": measurement,
                     "wrist": scene.measure_fixture_endpoint(self.parent, "microwave door", camera_view="wrist",
                                                              temporal_capture=True)}
        if getattr(ex, 'microwave_wrist_fixed_roi_v1', False):
            views = self.refine_wrist_fixed_roi(views)
        clearance = _public_robot_clearance(ex.p._last_obs_eef_pos, self.parent)
        occlusion = {camera: self._robot_occlusion(camera, view) for camera, view in views.items()}
        wrist = views.get('wrist', {})
        original = wrist.pop('_roi_original_view', None)
        if original is not None:
            guidance = wrist['fixed_roi_guidance']
            guidance['fusion_promoted'] = occlusion['wrist']['occluded'] is False
            if not guidance['fusion_promoted']:
                # An unmeasured new camera must not poison previously measured
                # agentview evidence. Keep the diagnosis, not a fused verdict.
                original['fixed_roi_guidance'] = guidance
                views['wrist'] = original
                occlusion['wrist'] = self._robot_occlusion('wrist', original)
        sample = combine_public_planes(views, state, self.parent)
        contributing = set((sample.get("frame") or {}).get("source_cameras", [])) | set(
            (sample.get("moving") or {}).get("source_cameras", []))
        flags = [occlusion[camera]["occluded"] for camera in contributing]
        unobstructed = bool(flags) and all(flag is False for flag in flags)
        artifacts = {}
        for camera in CAMERAS:
            # The ordinary record stores 256px K, while these RGB-D maps are
            # 1024px. Persist the public high-resolution calibration explicitly.
            camera_name = "agentview" if camera == "agentview" else "robot0_eye_in_hand"
            metadata = ex.p.env.get_camera_meta(camera_name, height=1024, width=1024)
            if metadata is None:
                raise RuntimeError(f"{camera} public high-resolution calibration missing")
            metadata_name = f"microwave_{camera}_metadata_high.json"
            if state.save(metadata_name, metadata, step=state.latest_step) is None:
                raise RuntimeError("could not persist public microwave camera calibration")
            artifacts[camera] = {
                "rgb": _identity(state.artifact_path(f"{camera}_high.png", step=state.latest_step)),
                "world": _identity(state.artifact_path(f"{camera}_world_high.npz", step=state.latest_step)),
                "calibration": _identity(state.artifact_path(metadata_name, step=state.latest_step)),
                "calibration_source": "public_env_camera_metadata_current_capture",
            }
        sample.update(timestamp_s=timestamp, capture_version=VERSION,
                      arm_withdrawn=bool(clearance["clear"] and withdrawal.get("reason") != "fixture_grip_not_released"),
                      occluded=False if unobstructed else True if any(flag is True for flag in flags) else None,
                      proprioception=clearance, withdrawal=copy.deepcopy(withdrawal), robot_mask_evidence=occlusion,
                      artifacts=artifacts)
        return sample

    def refine_wrist_fixed_roi(self, views):
        """Supply an optional wrist reference from real depth, preserving good fits."""
        from robots.libero.v5_microwave_wrist_roi import fit_wrist_fixed_roi

        views = copy.deepcopy(views)
        agent, wrist = views.get('agentview', {}), views.get('wrist', {})
        reference = agent.get('frame')
        if wrist.get('frame') or not reference:
            return views
        state, scene = self.executor.toolkit._state, self.executor.scene
        fit, evidence, cloud, mask = fit_wrist_fixed_roi(
            state.load('wrist_world_high.npz'), reference, _load_cloud(reference), source_step=state.latest_step)
        wrist['fixed_roi_guidance'] = evidence
        if fit is None:
            return views
        # Refresh the scene's public patch anchor from wrist points, then allow
        # its existing wrist SAM/consensus path to remeasure the moving panel.
        lo, hi = np.quantile(cloud, (.02, .98), axis=0)
        scene._microwave_frame_anchors[(self.parent.id, 'wrist')] = {
            'lower': lo.tolist(), 'upper': hi.tolist(), 'source_step': state.latest_step, 'parent': self.parent.id}
        repeated = scene.measure_fixture_endpoint(self.parent, 'microwave door', camera_view='wrist', temporal_capture=True)
        identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
        name = f'microwave_wrist_fixed_roi_{self.parent.id}_{identity}.npz'
        mask_name = f'microwave_wrist_fixed_roi_{self.parent.id}_{identity}_mask.npz'
        if state.save(name, cloud, step=state.latest_step) is None or state.save(mask_name, mask, step=state.latest_step) is None:
            raise RuntimeError('could not persist current wrist ROI points and mask')
        frame = {**fit, **_identity(state.artifact_path(name, step=state.latest_step)),
            'source': 'perception', 'frame_id': 'world', 'length_unit': 'm', 'source_step': state.latest_step,
            'source_cameras': ['wrist'], 'mask_count': 1,
            'mask_artifact': _identity(state.artifact_path(mask_name, step=state.latest_step)),
            'roi_guidance': evidence}
        # Preserve the original measured moving face if re-query missed it.
        if wrist.get('moving'):
            repeated['moving'] = wrist['moving']
        repeated['frame'] = frame
        repeated['fixed_roi_guidance'] = evidence
        repeated['_roi_original_view'] = wrist
        moving_mask = (repeated.get('moving') or {}).get('mask_artifact')
        repeated['frame_moving_mask_overlap'] = None
        if moving_mask:
            with np.load(moving_mask['path'], allow_pickle=False) as saved:
                moving = saved['array'].astype(bool)
            if moving.shape == mask.shape:
                repeated['frame_moving_mask_overlap'] = float(np.count_nonzero(mask & moving)
                    / max(1, min(np.count_nonzero(mask), np.count_nonzero(moving))))
        views['wrist'] = repeated
        return views

    def readonly_clearance(self):
        """Read robot sensors without sending motion, gripper or hold controls."""
        return {"version": READONLY_PROBE_VERSION, "reason": "readonly_public_probe", "moves": [],
                "control_count": 0, "after": _public_robot_clearance(self.executor.p._last_obs_eef_pos, self.parent)}

    def capture_pair(self, *, withdraw_before=True):
        withdrawal = self.withdraw() if withdraw_before else self.readonly_clearance()
        observation_pose = None
        if self.observation_pose_enabled and withdraw_before:
            # This planning capture may be occluded; it only supplies current
            # independent plane measurements for movement, never a verdict.
            observation_pose = self.observation_pose(self.capture(withdrawal))
        pair = [self.capture(withdrawal)]
        p = self.executor.p
        controls = 0
        for _ in range(math.ceil(self.interval_s / self.control_dt_s)):
            if p.env.terminated or p.env.truncated:
                break
            p._step_env(np.zeros(7, dtype=np.float32))
            controls += 1
        pair.append(self.capture(withdrawal))
        if observation_pose is not None:
            for sample in pair:
                sample["observation_pose"] = copy.deepcopy(observation_pose)
        pair[-1]["interval_controls"] = controls
        pair[-1]["control_dt_s"] = self.control_dt_s
        # If the environment interrupts the hold, do not claim a 0.3s interval
        # merely because segmentation consumed sufficient wall-clock time.
        if controls * self.control_dt_s + 1e-9 < self.interval_s:
            pair[-1]["occluded"] = None
            pair[-1]["interval_reason"] = "execution_interrupted_before_stability_interval"
        return pair

    def start(self):
        # A single SAM miss must not poison the fixed baseline for every later
        # block. Re-capture publicly before contact, retaining each bad pair;
        # absence of a robot mask still means unknown, never unobstructed.
        for attempt in range(1, BASELINE_CAPTURE_MAX_PAIRS + 1):
            self.before = (self.capture_pair(withdraw_before=False) if self.readonly_probe_enabled
                           else self.capture_pair())
            measured = measure_microwave_capture_pair(self.before)
            self.records.append({"phase": "before", "baseline_attempt": attempt,
                                 "frames": self.before, "measurement": measured})
            if measured["status"] == "measured":
                break

    def observe(self, chunks):
        if chunks % self.every_chunks:
            return {"stop_admitted": False, "status": "not_sampled"}
        if self.readonly_probe_enabled:
            frame = self.capture(self.readonly_clearance())
            candidate = public_endpoint_candidate(frame, self.mode)
            self.records.append({"phase": "probe", "chunks": chunks, "frames": [frame],
                                 "measurement": candidate, "intervening_controls": 0})
            if not candidate["endpoint_candidate"]:
                return candidate
            # A single frame can only trigger confirmation. Release/withdraw
            # and the real 0.3s hold occur only after this public candidate.
        after = self.capture_pair()
        evidence = measure_microwave_door_temporal(self.before, after, self.mode,
                                                 endpoint_stop_enabled=self.stop_enabled)
        evidence["stop_reason"] = "microwave_temporal_endpoint_verified"
        self.records.append({"phase": "after", "chunks": chunks, "frames": after, "measurement": evidence})
        return evidence


def make_microwave_public_stop(executor, parent, mode, *, stop_enabled=False, every_chunks=1):
    """Return the callback used by ``vla_act(public_stop=...)`` and its ledger."""
    collector = MicrowaveEndpointCapture(executor, parent, mode, stop_enabled=stop_enabled,
                                        every_chunks=every_chunks,
                                        observation_pose_enabled=getattr(executor, "microwave_observation_pose_v1", False),
                                        readonly_probe_enabled=getattr(executor, "microwave_readonly_probe_v1", False))
    collector.start()
    return collector.observe, collector.records
