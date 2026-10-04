# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Shared measured-AABB projection for training frames and runtime media.

Camera metadata follows RPent's depth back-projection convention: positive
camera z points forward. Bounds come from perception, never simulator bodies.
"""

from __future__ import annotations

import base64
import hashlib
import io
import itertools
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

VERSION = "measured-set-of-mark/1"
VIEWS = ("agentview", "wrist")


def project_bounds(entity: dict, metadata: dict, image_size: tuple[int, int]) -> list[int] | None:
    """Project and clip a measured world AABB, including near-plane edges."""
    if not re.fullmatch(r"e[0-9]+", entity["id"]):
        raise ValueError("marks must use the public entity ID")
    if str(entity.get("src", "perception")).startswith("sim"):
        raise ValueError("simulator geometry cannot supply an image mark")
    bounds = np.array([entity["lower"], entity["upper"]], dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all() or (bounds[0] > bounds[1]).any():
        raise ValueError("invalid measured AABB")
    corners = np.array(list(itertools.product(*zip(*bounds))))
    transform = np.asarray(metadata["extrinsic_cam2world"], dtype=float)
    intrinsic = np.asarray(metadata["intrinsic_K"], dtype=float).copy()
    if transform.shape != (4, 4) or intrinsic.shape != (3, 3):
        raise ValueError("invalid camera calibration")
    if not np.isfinite(transform).all() or not np.isfinite(intrinsic).all():
        raise ValueError("nonfinite camera calibration")
    camera = (np.column_stack([corners, np.ones(8)]) @ np.linalg.inv(transform).T)[:, :3]
    near = 1e-5
    points = [p for p in camera if p[2] >= near]
    for i, j in itertools.combinations(range(8), 2):
        if np.count_nonzero(corners[i] != corners[j]) != 1:
            continue
        a, b = camera[i], camera[j]
        if (a[2] < near) != (b[2] < near):
            points.append(a + (b - a) * ((near - a[2]) / (b[2] - a[2])))
    if not points:
        return None
    width, height = image_size
    intrinsic[0] *= width / metadata["width"]
    intrinsic[1] *= height / metadata["height"]
    homogeneous = np.asarray(points) @ intrinsic.T
    pixels = homogeneous[:, :2] / homogeneous[:, 2:3]
    lo, hi = pixels.min(axis=0), pixels.max(axis=0)
    if hi[0] < 0 or hi[1] < 0 or lo[0] >= width or lo[1] >= height:
        return None
    box = [max(0, int(np.floor(lo[0]))), max(0, int(np.floor(lo[1]))),
           min(width, int(np.ceil(hi[0]))), min(height, int(np.ceil(hi[1])))]
    return box if box[0] < box[2] and box[1] < box[3] else None


def render_marks(image_bytes: bytes, metadata: dict, entities: list[dict]) -> tuple[bytes, dict]:
    """Draw public IDs using the identical projector in training and serving."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    marks = []
    for entity in entities:
        box = project_bounds(entity, metadata, image.size)
        if box is None:
            continue
        draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), outline=(255, 216, 0), width=3)
        label = entity["id"]
        x, y = box[:2]
        text_box = draw.textbbox((x, y), label)
        draw.rectangle(text_box, fill=(0, 0, 0))
        draw.text((x, y), label, fill=(255, 216, 0))
        marks.append({"id": label, "box_xyxy": box, "source_step": entity.get("source_step"),
                      "src": entity.get("src", "perception")})
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), {"version": VERSION, "width": image.width, "height": image.height,
                              "marks": marks, "image_sha256": hashlib.sha256(image_bytes).hexdigest()}


def render_pair(output: Path, step: int, artifacts: list[str], entities: list[dict],
                destination: Path) -> dict:
    """Read only explicitly registered frame artifacts and save both marks."""
    destination.mkdir(parents=True, exist_ok=True)
    views = []
    for view in VIEWS:
        image_name, calibration_name = f"{view}_high.png", f"{view}_metadata.json"
        if image_name not in artifacts or calibration_name not in artifacts:
            raise ValueError(f"missing registered {view} decision image/calibration")
        import json
        image_path = output / image_name / f"{step:02d}.png"
        metadata_path = output / calibration_name / f"{step:02d}.json"
        metadata = json.loads(metadata_path.read_text())
        marked, detail = render_marks(image_path.read_bytes(), metadata, entities)
        marked_path = destination / f"{view}.png"
        marked_path.write_bytes(marked)
        views.append({"view": view, "path": str(marked_path.resolve()),
                      "sha256": hashlib.sha256(marked).hexdigest(),
                      "original_image": str(image_path), "calibration": str(metadata_path),
                      "calibration_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(), **detail})
    return {"version": VERSION, "frame_step": step, "views": views}


def wire_media(pair: dict) -> dict:
    """Project v6 extension: two ordered PNGs, with no simulator metadata."""
    images = []
    for view in pair["views"]:
        data = Path(view["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != view["sha256"]:
            raise ValueError("marked image changed after capture")
        images.append({"view": view["view"], "mime_type": "image/png",
                       "data": base64.b64encode(data).decode("ascii")})
    if [item["view"] for item in images] != list(VIEWS):
        raise ValueError("media requires agentview then wrist")
    return {"images": images}
