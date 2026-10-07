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
    measure_microwave_capture_pair, measure_microwave_door_temporal,
)
from robots.libero.v5_verification import vertical_face


VERSION = "microwave-public-dual-temporal-capture/1-dev"
CAMERAS = ("agentview", "wrist")
BASELINE_CAPTURE_MAX_PAIRS = 3


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
                 interval_s=.3, control_dt_s=.05):
        if parent.name != "microwave" or mode not in ("open", "close"):
            raise ValueError("microwave capture requires a measured microwave and open/close mode")
        if every_chunks < 1 or interval_s < .3 or control_dt_s <= 0:
            raise ValueError("invalid microwave capture interval")
        self.executor, self.parent, self.mode = executor, parent, mode
        self.stop_enabled, self.every_chunks = bool(stop_enabled), int(every_chunks)
        self.interval_s, self.control_dt_s = float(interval_s), float(control_dt_s)
        self.records, self.before = [], []

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
        sample = combine_public_planes(views, state, self.parent)
        clearance = _public_robot_clearance(ex.p._last_obs_eef_pos, self.parent)
        occlusion = {camera: self._robot_occlusion(camera, view) for camera, view in views.items()}
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

    def capture_pair(self):
        withdrawal = self.withdraw()
        pair = [self.capture(withdrawal)]
        p = self.executor.p
        controls = 0
        for _ in range(math.ceil(self.interval_s / self.control_dt_s)):
            if p.env.terminated or p.env.truncated:
                break
            p._step_env(np.zeros(7, dtype=np.float32))
            controls += 1
        pair.append(self.capture(withdrawal))
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
            self.before = self.capture_pair()
            measured = measure_microwave_capture_pair(self.before)
            self.records.append({"phase": "before", "baseline_attempt": attempt,
                                 "frames": self.before, "measurement": measured})
            if measured["status"] == "measured":
                break

    def observe(self, chunks):
        if chunks % self.every_chunks:
            return {"stop_admitted": False, "status": "not_sampled"}
        after = self.capture_pair()
        evidence = measure_microwave_door_temporal(self.before, after, self.mode,
                                                 endpoint_stop_enabled=self.stop_enabled)
        evidence["stop_reason"] = "microwave_temporal_endpoint_verified"
        self.records.append({"phase": "after", "chunks": chunks, "frames": after, "measurement": evidence})
        return evidence


def make_microwave_public_stop(executor, parent, mode, *, stop_enabled=False, every_chunks=1):
    """Return the callback used by ``vla_act(public_stop=...)`` and its ledger."""
    collector = MicrowaveEndpointCapture(executor, parent, mode, stop_enabled=stop_enabled,
                                        every_chunks=every_chunks)
    collector.start()
    return collector.observe, collector.records
