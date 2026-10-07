"""Public RGB-D/proprio temporal features and CPU endpoint inference."""

from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image


VERSION = "public-rgbd-proprio-temporal/1-dev"
CAMERAS = ("agentview", "wrist")
GRID = 8


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def frame_features(public_frame, measured_bounds):
    """Pool two measured fixture crops; unavailable views stay masked."""
    lower, upper = np.asarray(measured_bounds["lower"]), np.asarray(measured_bounds["upper"])
    extent = upper - lower
    padding = np.maximum(extent * .25, [.04, .04, .04])
    lo, hi = lower - padding, upper + padding
    vectors, availability = [], []
    for camera in CAMERAS:
        view = public_frame.get("views", {}).get(camera, {})
        if "raw_rgb" not in view or "raw_world" not in view:
            vectors.append(np.zeros(GRID * GRID * 5, dtype=np.float32))
            availability.append(False)
            continue
        image = np.asarray(Image.open(view["raw_rgb"]["path"]).convert("RGB"))
        with np.load(view["raw_world"]["path"], allow_pickle=False) as world_file:
            world = np.asarray(world_file["array"], dtype=np.float32)
        if image.shape[:2] != world.shape[:2] or world.shape[-1] != 3:
            raise ValueError("public RGB-D shape mismatch")
        mask = np.isfinite(world).all(axis=-1) & (world >= lo).all(axis=-1) & (world <= hi).all(axis=-1)
        ys, xs = np.where(mask)
        if len(ys) < 100:
            vectors.append(np.zeros(GRID * GRID * 5, dtype=np.float32))
            availability.append(False)
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = image[y0:y1, x0:x1].astype(np.float32) / 255
        visible = mask[y0:y1, x0:x1]
        z = np.clip((world[y0:y1, x0:x1, 2] - lower[2]) / max(float(extent[2]), .03), -3, 3)
        z[~visible] = 0
        channels = [crop[..., k] for k in range(3)] + [z, visible.astype(np.float32)]
        vectors.append(np.concatenate([np.asarray(Image.fromarray(c).resize((GRID, GRID), Image.Resampling.BILINEAR)).ravel() for c in channels]))
        availability.append(True)
    return np.concatenate(vectors).astype(np.float32), availability


def sequence_features(before, recent, proprio):
    """Use before and three recent public frames; no clock/state ID features."""
    if not recent:
        raise ValueError("temporal sequence requires a current frame")
    frames = [before] + [recent[max(0, len(recent) - 3 + k)] for k in range(3)]
    values = [f["features"] for f in frames]
    flags = np.asarray([v for f in frames for v in f["available"]], dtype=np.float32)
    positions = np.asarray(proprio["recent_eef_xyz_m"], dtype=np.float32)
    openings = np.asarray(proprio["recent_gripper_opening_m"], dtype=np.float32)
    if positions.shape != (3, 3) or openings.shape != (3,):
        raise ValueError("expected three public robot observations")
    deltas = np.concatenate([(positions[-1] - positions[0]) / .1,
        (positions[-1] - np.asarray(proprio["before_eef_xyz_m"])) / .1,
        openings / .1, [float(openings[-1] - openings[0]) / .1]])
    return np.concatenate([*values, flags, deltas]).astype(np.float32)


def infer(sequence_vector, current_available, model_path):
    """Return unknown on missing observations; prediction never controls stop."""
    if not any(current_available):
        return {"status": "unknown", "p_satisfied": None, "reason": "fixture_unmeasured_in_both_views", "version": VERSION}
    with np.load(model_path, allow_pickle=False) as model:
        x = (np.asarray(sequence_vector) - model["mean"]) / model["scale"]
        if "hidden_weight" in model.files:
            x = np.maximum(x @ model["hidden_weight"].T + model["hidden_bias"], 0)
        logit = float(x @ model["output_weight"].ravel() + model["output_bias"].item())
        p = 1 / (1 + np.exp(-np.clip(logit, -50, 50)))
    return {"status": "predicted", "p_satisfied": float(p), "version": VERSION,
            "stop_admitted": False, "reason": "development_model_has_no_confirmation_admission"}

