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
import io
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
STAGED_CANDIDATE_VERSION = 'microwave-public-staged-endpoint-candidate/1-dev'
IDENTITY_TRACKING_VERSION = "microwave-public-RGBD-door-identity-runtime/1-dev"


def stable_public_endpoint_candidates(history, *, control_dt_s=.05):
    """Authorize observation withdrawal only after stable real contact blocks."""
    config = MicrowaveDoorTemporalConfig()
    evidence = {'version': STAGED_CANDIDATE_VERSION, 'source': 'perception_and_executed_controls',
                'withdrawal_admitted': False, 'stop_admitted': False, 'candidates': len(history)}
    if len(history) < 2:
        return {**evidence, 'reason': 'waiting_more_public_candidates'}
    counts = [row['executed_controls'] for row in history]
    if any(type(count) is not int for count in counts) or any(b <= a for a, b in zip(counts, counts[1:])):
        return {**evidence, 'reason': 'distinct_executed_contact_controls_not_measured'}
    duration = (counts[-1] - counts[0]) * control_dt_s
    evidence.update(executed_interval_controls=counts[-1] - counts[0], actual_contact_interval_s=duration)
    if duration + 1e-9 < config.minimum_interval_s:
        return {**evidence, 'reason': 'waiting_actual_contact_interval'}
    frames = [row['frame'] for row in history]
    if any(b['source_step'] <= a['source_step'] for a, b in zip(frames, frames[1:])):
        return {**evidence, 'reason': 'candidate_captures_not_distinct'}
    anchor = np.asarray(history[0]['candidate']['measured_planes']['frame']['normal_xy'])
    fixed = [row['candidate']['measured_planes']['frame'] for row in history]
    angles = [math.degrees(math.acos(float(np.clip(abs(anchor @ face['normal_xy']), 0., 1.)))) for face in fixed]
    drifts = [abs(float((np.asarray(face['centre'][:2]) - fixed[0]['centre'][:2]) @ anchor)) for face in fixed]
    door_angles = [row['candidate']['relative_angle_deg'] for row in history]
    relative = np.asarray([np.asarray(row['candidate']['measured_planes']['moving']['centre'])
                           - row['candidate']['measured_planes']['frame']['centre'] for row in history])
    displacement = float(np.linalg.norm(relative[:, None] - relative, axis=-1).max())
    evidence.update(reference_maximum_angle_deg=max(angles), reference_maximum_normal_drift_m=max(drifts),
        door_angle_range_deg=float(np.ptp(door_angles)), maximum_relative_centre_displacement_m=displacement)
    if max(angles) > config.maximum_reference_angle_deg or max(drifts) > config.maximum_reference_drift_m:
        return {**evidence, 'reason': 'independent_fixed_frame_not_stable'}
    if np.ptp(door_angles) > config.maximum_stable_angle_deg or displacement > config.maximum_stable_displacement_m:
        return {**evidence, 'reason': 'endpoint_candidate_still_moving'}
    return {**evidence, 'reason': 'public_candidate_stable_across_executed_contact_blocks', 'withdrawal_admitted': True}


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


def combine_public_planes(views, state, parent, *, occlusion=None):
    """Fuse unique measured per-view planes while retaining independence evidence."""
    sample = {"source": "perception", "frame_id": "world", "length_unit": "m",
              "source_step": state.latest_step, "source_cameras": [], "views": views,
              "fusion_version": "rgbd_dual_view/1", "frame": None, "moving": None,
              "frame_moving_mask_overlap": None, "measurement_counts": {}}
    if occlusion is not None:
        sample["measurement_view_admission"] = {
            camera: "current_robot_mask_clear" if occlusion.get(camera, {}).get("occluded") is False
            else "occluded_or_clearance_unmeasured" for camera in views
        }
        # Keep both raw camera records. Only the current, explicitly clear
        # views may contribute to this endpoint fit; an unknown wrist view
        # cannot erase an independently measured unobstructed agent view.
        views = {camera: view for camera, view in views.items()
                 if occlusion.get(camera, {}).get("occluded") is False}
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


def _public_rgbd(state, camera):
    """Load the current explicit public RGB-D capture for one camera."""
    from PIL import Image

    rgb = np.asarray(Image.open(io.BytesIO(state.load_bytes(f"{camera}_high.png"))).convert("RGB"))
    world = np.asarray(state.load(f"{camera}_world_high.npz"))
    if rgb.shape[:2] != world.shape[:2] or world.shape[-1] != 3:
        raise ValueError("public RGB-D camera shapes differ")
    return rgb, world


def _record_mask(record):
    identity = record.get("mask_artifact") if isinstance(record, dict) else None
    if not isinstance(identity, dict) or not identity.get("path"):
        return None
    with np.load(identity["path"], allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError("tracked door mask requires one explicit array")
        return np.asarray(saved[saved.files[0]]).astype(bool)


def _stable_frame_anchor(record, cloud):
    if not isinstance(record, dict) or cloud is None:
        return None
    points = np.asarray(cloud, dtype=float)
    points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
    if len(points) < 60:
        return None
    lo, hi = np.quantile(points, (.02, .98), axis=0)
    return {"lower": lo.tolist(), "upper": hi.tolist(),
            "source_step": record.get("source_step")}


class MicrowaveEndpointCapture:
    """Capture two fresh unobstructed views per phase and check between blocks."""

    def __init__(self, executor, parent, mode, *, stop_enabled=False, every_chunks=1,
                 interval_s=.3, control_dt_s=.05, observation_pose_enabled=False,
                 readonly_probe_enabled=False, staged_candidate_enabled=False,
                 identity_tracking_enabled=False, candidate_hold_enabled=False):
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
        self.staged_candidate_enabled = bool(staged_candidate_enabled)
        self.identity_tracking_enabled = bool(identity_tracking_enabled)
        self.candidate_hold_enabled = bool(candidate_hold_enabled)
        self.candidate_history = []
        # One-step identity state only. A missing current measurement clears
        # this entry after the current capture, so a later frame cannot bridge
        # an occlusion or a camera restart with stale door geometry.
        self._identity_history = {camera: None for camera in CAMERAS}

    def _persist_tracked_moving(self, state, camera, current_world, mask, face):
        """Persist a tracked current cloud and mask as ordinary public evidence."""
        cloud = np.asarray(current_world)[mask]
        cloud = cloud[np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)]
        if len(cloud) < 30:
            return None
        digest = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
        name = f"microwave_temporal_{self.parent.id}_moving_{camera}_tracked_{digest}.npz"
        if state.save(name, cloud, step=state.latest_step) is None:
            raise RuntimeError("could not persist tracked microwave door cloud")
        path = state.artifact_path(name, step=state.latest_step)
        mask_name = f"microwave_temporal_{self.parent.id}_moving_{camera}_tracked_{digest}_mask.npz"
        if state.save(mask_name, mask.astype(bool), step=state.latest_step) is None:
            raise RuntimeError("could not persist tracked microwave door mask")
        mask_path = state.artifact_path(mask_name, step=state.latest_step)
        return {**face, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source": "perception", "frame_id": "world", "length_unit": "m",
                "source_step": state.latest_step, "source_cameras": [camera], "mask_count": 1,
                "mask_artifact": {"path": str(mask_path),
                    "sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest()},
                "identity_tracking_version": IDENTITY_TRACKING_VERSION}

    def _track_missing_views(self, views, occlusion):
        """Recover one-step moving-face identity from current public RGB-D.

        A current fixed frame must still be independently measured and stable
        against the previous fixed frame. The moving cloud is always sampled
        from the current RGB-D map; only identity correspondence comes from
        the previous frame. Unknown current views stay unknown.
        """
        if not self.identity_tracking_enabled:
            return views
        from robots.libero.v5_microwave_identity import track_measured_door

        state = self.executor.toolkit._state
        for camera in CAMERAS:
            view = views.get(camera)
            previous = self._identity_history.get(camera)
            if not isinstance(view, dict) or view.get("moving") is not None:
                continue
            if previous is None or view.get("frame") is None:
                view.setdefault("identity_tracking", {
                    "version": IDENTITY_TRACKING_VERSION, "camera": camera,
                    "source": "perception", "reason": (
                        "current_fixed_frame_not_measured" if view.get("frame") is None
                        else "previous_independent_door_identity_missing"),
                    "private_labels_used": False, "stop_admitted": False,
                })
                continue
            try:
                current_rgb, current_world = _public_rgbd(state, camera)
                frame_cloud = None
                frame_identity = view["frame"].get("path")
                if frame_identity:
                    with np.load(frame_identity, allow_pickle=False) as saved:
                        if len(saved.files) == 1:
                            frame_cloud = np.asarray(saved[saved.files[0]])
                anchor = previous.get("anchor")
                current_frame = view["frame"]
                prev_frame = previous.get("frame")
                if anchor is None or prev_frame is None:
                    raise ValueError("previous independent fixed frame missing")
                # Fixed-frame stability is checked before accepting tracked
                # moving points. This prevents a changed camera or parent
                # binding from being treated as a door displacement.
                normal = np.asarray(prev_frame.get("normal_xy"), dtype=float)
                current_normal = np.asarray(current_frame.get("normal_xy"), dtype=float)
                if normal.shape != (2,) or current_normal.shape != (2,):
                    raise ValueError("fixed frame normal missing")
                angle = math.degrees(math.acos(float(np.clip(abs(normal @ current_normal), 0., 1.))))
                drift = abs(float((np.asarray(current_frame["centre"][:2])
                                   - np.asarray(prev_frame["centre"][:2])[:2]) @ normal))
                if angle > .10 or drift > .01:
                    raise ValueError("current fixed frame is not stable")
                mask = previous.get("moving_mask")
                if mask is None:
                    raise ValueError("previous moving identity mask missing")
                robot_identity = (occlusion.get(camera) or {}).get("robot_mask_artifact")
                robot_mask = None
                if robot_identity:
                    with np.load(robot_identity["path"], allow_pickle=False) as saved:
                        if len(saved.files) == 1:
                            robot_mask = np.asarray(saved[saved.files[0]]).astype(bool)
                tracked_mask, face, evidence = track_measured_door(
                    previous["rgb"], current_rgb, previous["world"], current_world,
                    mask, anchor, robot_mask=robot_mask)
                evidence.update(version=IDENTITY_TRACKING_VERSION,
                                camera=camera, source_step=state.latest_step,
                                previous_source_step=previous.get("source_step"),
                                fixed_frame_angle_deg=angle, fixed_frame_drift_m=drift,
                                private_labels_used=False, stop_admitted=False)
                view["identity_tracking"] = evidence
                if face is not None:
                    tracked = self._persist_tracked_moving(state, camera, current_world, tracked_mask, face)
                    if tracked is not None:
                        view["moving"] = tracked
                        frame_mask = _record_mask(view.get("frame"))
                        if frame_mask is not None and frame_mask.shape == tracked_mask.shape:
                            view["frame_moving_mask_overlap"] = float(
                                np.count_nonzero(frame_mask & tracked_mask)
                                / max(1, min(np.count_nonzero(frame_mask), np.count_nonzero(tracked_mask))))
            except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
                view["identity_tracking"] = {
                    "version": IDENTITY_TRACKING_VERSION, "camera": camera,
                    "source": "perception", "reason": "tracking_error",
                    "error": repr(error), "private_labels_used": False,
                    "stop_admitted": False,
                }
        return views

    def _update_identity_history(self, views, public_rgbd):
        """Keep only the immediately preceding measured identity per camera."""
        if not self.identity_tracking_enabled:
            return
        state = self.executor.toolkit._state
        for camera in CAMERAS:
            view = views.get(camera)
            if not isinstance(view, dict) or view.get("frame") is None or view.get("moving") is None:
                self._identity_history[camera] = None
                continue
            try:
                moving_mask = _record_mask(view["moving"])
                frame_cloud = None
                with np.load(view["frame"]["path"], allow_pickle=False) as saved:
                    if len(saved.files) == 1:
                        frame_cloud = np.asarray(saved[saved.files[0]])
                anchor = _stable_frame_anchor(view["frame"], frame_cloud)
                if moving_mask is None or anchor is None:
                    self._identity_history[camera] = None
                    continue
                rgb, world = public_rgbd[camera]
                self._identity_history[camera] = {
                    "rgb": np.array(rgb, copy=True), "world": np.array(world, copy=True),
                    "moving_mask": np.array(moving_mask, copy=True),
                    "frame": copy.deepcopy(view["frame"]), "anchor": anchor,
                    "source_step": state.latest_step,
                }
            except (OSError, KeyError, TypeError, ValueError, IndexError):
                self._identity_history[camera] = None

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
        if not robot_masks or not measurement.get("frame"):
            return evidence
        region_masks = []
        region_names = []
        for kind in ("frame", "moving"):
            if not measurement.get(kind):
                continue
            mask_identity = measurement[kind].get("mask_artifact")
            if not mask_identity:
                return evidence
            with np.load(mask_identity["path"], allow_pickle=False) as saved:
                mask = saved["array"]
            if mask.shape != world.shape[:2]:
                return evidence
            region_names.append(kind)
            region_masks.append(mask.astype(bool))
        if not region_masks:
            return evidence
        robot = np.logical_or.reduce(robot_masks)
        name = f"microwave_temporal_robot_{camera}_mask.npz"
        if state.save(name, robot, step=state.latest_step) is None:
            raise RuntimeError("could not persist current public robot occlusion mask")
        fractions = [float(np.count_nonzero(robot & mask) / max(1, np.count_nonzero(mask))) for mask in region_masks]
        evidence.update(overlap_by_region=dict(zip(region_names, fractions)),
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
        public_rgbd = {}
        if self.identity_tracking_enabled:
            for camera in CAMERAS:
                try:
                    public_rgbd[camera] = _public_rgbd(state, camera)
                except (OSError, KeyError, TypeError, ValueError) as error:
                    public_rgbd[camera] = None
                    views.setdefault(camera, {})["identity_tracking"] = {
                        "version": IDENTITY_TRACKING_VERSION, "camera": camera,
                        "source": "perception", "reason": "current_public_rgbd_missing",
                        "error": repr(error), "private_labels_used": False,
                        "stop_admitted": False,
                    }
            views = self._track_missing_views(views, occlusion)
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
        sample = combine_public_planes(views, state, self.parent,
            occlusion=occlusion if getattr(ex, "microwave_verified_view_fusion_v1", False) else None)
        if self.identity_tracking_enabled:
            self._update_identity_history(views, public_rgbd)
            sample["identity_tracking_version"] = IDENTITY_TRACKING_VERSION
            sample["identity_tracking_cameras"] = {
                camera: (views.get(camera, {}).get("identity_tracking") or {}).get(
                    "reason", "independent" if views.get(camera, {}).get("moving") is not None
                    else "current_door_not_measured")
                for camera in CAMERAS
            }
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
            if self.staged_candidate_enabled:
                if candidate['endpoint_candidate']:
                    traces = getattr(self.executor, 'motion_evidence', [])
                    counts = [trace.get('executed_action_count') for trace in traces
                              if trace.get('name') == 'vla_act_chunk']
                    controls = sum(counts) if counts and all(type(count) is int and count > 0 for count in counts) else None
                    self.candidate_history.append({'frame': frame, 'candidate': copy.deepcopy(candidate),
                                                    'executed_controls': controls})
                    self.candidate_history = self.candidate_history[-3:]
                    staged = stable_public_endpoint_candidates(self.candidate_history, control_dt_s=self.control_dt_s)
                    if staged['reason'] in ('endpoint_candidate_still_moving', 'independent_fixed_frame_not_stable'):
                        self.candidate_history = self.candidate_history[-1:]
                else:
                    self.candidate_history = []
                    staged = {'version': STAGED_CANDIDATE_VERSION, 'withdrawal_admitted': False,
                              'stop_admitted': False, 'reason': 'current_endpoint_candidate_not_measured'}
                candidate['staged_confirmation'] = staged
            self.records.append({"phase": "probe", "chunks": chunks, "frames": [frame],
                                 "measurement": candidate, "intervening_controls": 0})
            if not candidate["endpoint_candidate"]:
                return candidate
            if self.candidate_hold_enabled:
                # Pause contact at a publicly measured candidate. Continuing
                # another VLA block can undo the endpoint before SAM recovers
                # a missing mask. A real neutral hold supplies the same
                # stability evidence without another contact-policy action.
                pair = self.capture_pair(withdraw_before=False)
                held_candidates = [public_endpoint_candidate(sample, self.mode) for sample in pair]
                controls = pair[-1].get("interval_controls")
                if all(row["endpoint_candidate"] for row in held_candidates):
                    staged = stable_public_endpoint_candidates([
                        {"frame": sample, "candidate": row, "executed_controls": count}
                        for sample, row, count in zip(pair, held_candidates, (0, controls))
                    ], control_dt_s=self.control_dt_s)
                else:
                    staged = {"withdrawal_admitted": False, "stop_admitted": False,
                              "reason": "current_hold_endpoint_not_measured"}
                self.records.append({"phase": "candidate_hold", "chunks": chunks,
                                     "frames": pair, "measurement": staged,
                                     "candidates": held_candidates, "intervening_controls": controls})
                if not staged["withdrawal_admitted"]:
                    return {**candidate, "hold_confirmation": staged}
            elif self.staged_candidate_enabled and not candidate['staged_confirmation']['withdrawal_admitted']:
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
                                        readonly_probe_enabled=getattr(executor, "microwave_readonly_probe_v1", False),
                                        staged_candidate_enabled=getattr(executor, 'microwave_staged_candidate_v1', False),
                                        identity_tracking_enabled=getattr(executor, 'microwave_identity_tracking_v1', False),
                                        candidate_hold_enabled=getattr(executor, 'microwave_candidate_hold_v2', False))
    collector.start()
    return collector.observe, collector.records
