# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Public RGB-D/proprioception temporal endpoint verification.

This module is deliberately independent of simulator state.  It consumes only
the RGB-D artifacts and robot proprioception that the runtime already exposes.
Missing or malformed observations remain ``unknown`` and therefore cannot
authorize an early primitive stop.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from zipfile import BadZipFile

import numpy as np
from PIL import Image


VERSION = "public-rgbd-proprio-temporal/1-dev"
CAMERAS = ("agentview", "wrist")
GRID = 8


def identity(path: str | Path) -> dict:
    """Return a reproducible public artifact identity."""
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _view_features(view: dict, measured_bounds: dict) -> tuple[np.ndarray, bool]:
    """Pool one measured fixture crop, returning an unavailable mask on error."""
    try:
        lower = np.asarray(measured_bounds["lower"], dtype=float)
        upper = np.asarray(measured_bounds["upper"], dtype=float)
        extent = upper - lower
        padding = np.maximum(extent * .25, [.04, .04, .04])
        lo, hi = lower - padding, upper + padding
        image = np.asarray(Image.open(view["raw_rgb"]["path"]).convert("RGB"))
        with np.load(view["raw_world"]["path"], allow_pickle=False) as world_file:
            world = np.asarray(world_file["array"], dtype=np.float32)
        if image.shape[:2] != world.shape[:2] or world.ndim != 3 or world.shape[-1] != 3:
            raise ValueError("public RGB-D shape mismatch")
        mask = np.isfinite(world).all(axis=-1) & (world >= lo).all(axis=-1) & (world <= hi).all(axis=-1)
        ys, xs = np.where(mask)
        if len(ys) < 100:
            raise ValueError("fixture crop has insufficient measured points")
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = image[y0:y1, x0:x1].astype(np.float32) / 255
        visible = mask[y0:y1, x0:x1]
        z = np.clip((world[y0:y1, x0:x1, 2] - lower[2]) / max(float(extent[2]), .03), -3, 3)
        z[~visible] = 0
        channels = [crop[..., k] for k in range(3)] + [z, visible.astype(np.float32)]
        vector = np.concatenate([
            np.asarray(Image.fromarray(channel).resize((GRID, GRID), Image.Resampling.BILINEAR)).ravel()
            for channel in channels
        ])
        return vector.astype(np.float32), True
    except (OSError, BadZipFile, KeyError, ValueError, TypeError, IndexError):
        return np.zeros(GRID * GRID * 5, dtype=np.float32), False


def frame_features(public_frame: dict, measured_bounds: dict) -> tuple[np.ndarray, list[bool]]:
    """Pool both measured fixture crops; unavailable views stay masked."""
    vectors, available = [], []
    for camera in CAMERAS:
        vector, is_available = _view_features(public_frame.get("views", {}).get(camera, {}), measured_bounds)
        vectors.append(vector)
        available.append(is_available)
    return np.concatenate(vectors).astype(np.float32), available


def sequence_features(before: dict, recent: list[dict], proprio: dict) -> np.ndarray:
    """Build the registered before-plus-three-recent public feature vector."""
    if not recent:
        raise ValueError("temporal sequence requires a current frame")
    frames = [before] + [recent[max(0, len(recent) - 3 + k)] for k in range(3)]
    values = [np.asarray(frame["features"], dtype=np.float32) for frame in frames]
    flags = np.asarray([flag for frame in frames for flag in frame["available"]], dtype=np.float32)
    positions = np.asarray(proprio["recent_eef_xyz_m"], dtype=np.float32)
    openings = np.asarray(proprio["recent_gripper_opening_m"], dtype=np.float32)
    if positions.shape != (3, 3) or openings.shape != (3,):
        raise ValueError("expected three public robot observations")
    deltas = np.concatenate([
        (positions[-1] - positions[0]) / .1,
        (positions[-1] - np.asarray(proprio["before_eef_xyz_m"])) / .1,
        openings / .1,
        [float(openings[-1] - openings[0]) / .1],
    ])
    return np.concatenate([*values, flags, deltas]).astype(np.float32)


def feature_encoder_identity() -> str:
    """Identify exactly the encoder shared by offline preparation and runtime."""
    source = f"{VERSION}:{CAMERAS}:{GRID}\n" + "\n".join(
        inspect.getsource(function) for function in (_view_features, frame_features, sequence_features)
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def infer(sequence_vector: np.ndarray, current_available: list[bool], model_path: str | Path,
          *, threshold: float | None = None, requested_mode: str | None = None) -> dict:
    """Infer endpoint satisfaction without admitting a stop unless threshold is explicit."""
    base = {"version": VERSION, "stop_admitted": False}
    if not any(current_available):
        return {**base, "status": "unknown", "p_satisfied": None,
                "reason": "fixture_unmeasured_in_both_views"}
    try:
        with np.load(model_path, allow_pickle=False) as model:
            modes = model["supports_modes"].tolist()
            if requested_mode is None or requested_mode not in modes:
                return {**base, "status": "unknown", "p_satisfied": None,
                        "reason": "temporal_model_mode_not_supported", "requested_mode": requested_mode}
            if str(model["feature_encoder_sha256"].item()) != feature_encoder_identity():
                return {**base, "status": "unknown", "p_satisfied": None,
                        "reason": "temporal_feature_encoder_mismatch"}
            x = (np.asarray(sequence_vector, dtype=np.float32) - model["mean"]) / model["scale"]
            if not np.isfinite(x).all():
                raise ValueError("nonfinite temporal features")
            if "hidden_weight" in model.files:
                x = np.maximum(x @ model["hidden_weight"].T + model["hidden_bias"], 0)
            logit = float(x @ model["output_weight"].ravel() + model["output_bias"].item())
            p = float(1 / (1 + np.exp(-np.clip(logit, -50, 50))))
    except (OSError, BadZipFile, KeyError, ValueError, TypeError, IndexError):
        return {**base, "status": "unknown", "p_satisfied": None,
                "reason": "temporal_model_or_feature_error"}
    if threshold is None:
        reason = "development_model_has_no_confirmation_admission"
    elif p >= threshold:
        reason = "public_temporal_threshold_passed"
    else:
        reason = "public_temporal_threshold_not_met"
    return {**base, "status": "predicted", "p_satisfied": p,
            "stop_admitted": bool(threshold is not None and p >= threshold),
            "threshold": threshold, "reason": reason, "requested_mode": requested_mode}


def public_frame(executor, measured_bounds: dict) -> dict:
    """Capture identities for the current public RGB-D frame and proprioception."""
    state = getattr(getattr(executor, "toolkit", None), "_state", None)
    step = getattr(state, "latest_step", None)
    frame = {
        "source_step": step,
        "views": {},
        "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
        "private_object_or_joint_values": False,
    }
    if state is None or step is None:
        frame["public_robot_observation"] = None
        frame["features"], frame["available"] = frame_features(frame, measured_bounds)
        return frame
    for camera in CAMERAS:
        try:
            rgb = Path(state.artifact_path(f"{camera}_high.png", step=step))
            world = Path(state.artifact_path(f"{camera}_world_high.npz", step=step))
            if rgb.is_file() and world.is_file():
                frame["views"][camera] = {
                    "raw_rgb": identity(rgb), "raw_world": identity(world), "source_step": step,
                }
        except (OSError, ValueError, LookupError):
            continue
    try:
        eef = np.asarray(executor.p._last_obs_eef_pos, dtype=float).tolist()
        opening = float(executor.p._last_obs_gripper)
        frame["public_robot_observation"] = {
            "eef_xyz_m": eef, "gripper_opening_m": opening,
        }
    except (AttributeError, TypeError, ValueError):
        frame["public_robot_observation"] = None
    frame["features"], frame["available"] = frame_features(frame, measured_bounds)
    return frame


class TemporalEndpointVerifier:
    """Collect a public sequence and produce an opt-in stop signal."""

    def __init__(self, executor, measured_bounds: dict, model_path: str | Path,
                 threshold: float, capture_every: int = 1, *, requested_mode: str):
        if not (0 <= float(threshold) <= 1):
            raise ValueError("temporal endpoint threshold must be in [0, 1]")
        if int(capture_every) < 1:
            raise ValueError("temporal endpoint capture cadence must be >= 1")
        self.executor = executor
        self.measured_bounds = measured_bounds
        self.model_path = Path(model_path)
        self.threshold = float(threshold)
        self.capture_every = int(capture_every)
        self.requested_mode = requested_mode
        self.before: dict | None = None
        self.recent: list[dict] = []
        self.records: list[dict] = []
        self._last_frame: dict | None = None

    def _capture(self) -> dict:
        try:
            self.executor.capture()
        except (AttributeError, OSError, RuntimeError, ValueError):
            return {"source_step": None, "views": {}, "public_robot_observation": None,
                    "features": np.zeros(GRID * GRID * 10, dtype=np.float32),
                    "available": [False, False]}
        return public_frame(self.executor, self.measured_bounds)

    def start(self) -> dict:
        self.before = self._capture()
        self.recent = []
        evidence = {
            "version": VERSION, "status": "abstain", "stop_admitted": False,
            "reason": "need_three_current_public_frames", "source_step": self.before.get("source_step"),
        }
        self.records.append({"phase": "before", **evidence})
        return evidence

    def observe(self, chunks: int) -> dict:
        if chunks % self.capture_every:
            return {"version": VERSION, "status": "abstain", "stop_admitted": False,
                    "reason": "capture_cadence", "chunk": chunks}
        current = self._capture()
        self._last_frame = current
        self.recent.append(current)
        evidence = {
            "version": VERSION, "status": "abstain", "stop_admitted": False,
            "reason": "need_three_current_public_frames", "chunk": chunks,
            "source_step": current.get("source_step"),
            "available": current.get("available", []),
        }
        if self.before is not None and len(self.recent) >= 3:
            try:
                observations = [frame.get("public_robot_observation") for frame in self.recent[-3:]]
                if self.before.get("public_robot_observation") is None or any(item is None for item in observations):
                    raise ValueError("public robot observation unavailable")
                steps = [frame.get("source_step") for frame in self.recent[-3:]]
                if None in steps or len(set(steps)) != 3 or self.before.get("source_step") in steps:
                    raise ValueError("three fresh public frames unavailable")
                proprio = {
                    "before_eef_xyz_m": self.before["public_robot_observation"]["eef_xyz_m"],
                    "recent_eef_xyz_m": [item["eef_xyz_m"] for item in observations],
                    "recent_gripper_opening_m": [item["gripper_opening_m"] for item in observations],
                }
                vector = sequence_features(self.before, self.recent, proprio)
                evidence = {
                    **infer(vector, current.get("available", []), self.model_path,
                            threshold=self.threshold, requested_mode=self.requested_mode),
                    "chunk": chunks, "source_step": current.get("source_step"),
                    "available": current.get("available", []),
                }
                if evidence.get("stop_admitted"):
                    evidence["stop_reason"] = "temporal_endpoint_verified"
            except (KeyError, TypeError, ValueError):
                evidence["reason"] = "public_sequence_unavailable"
        self.records.append(evidence)
        return evidence
