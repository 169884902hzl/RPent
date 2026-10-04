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

VERSION = "measured-set-of-mark/4"
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


def visible_box(box: list[int], entity: dict, world_map: np.ndarray,
                mask: np.ndarray | None = None) -> tuple[list[int] | None, int]:
    """Keep only current RGB-D support within the projected measured bounds.

    A stale cached volume with no visible support is not a box on the image.
    The 2 mm margin accommodates measured quantiles and RGB-D roundoff.
    """
    x0, y0, x1, y1 = box
    points = world_map[y0:y1, x0:x1]
    supported = np.isfinite(points).all(axis=-1) & (np.abs(points).sum(axis=-1) > 1e-6)
    supported &= ((points >= np.asarray(entity["lower"]) - .002)
                  & (points <= np.asarray(entity["upper"]) + .002)).all(axis=-1)
    if mask is not None:
        supported &= mask[y0:y1, x0:x1]
    rows, columns = np.nonzero(supported)
    if len(rows) < 10:
        return None, len(rows)
    return [x0 + int(columns.min()), y0 + int(rows.min()),
            x0 + int(columns.max()) + 1, y0 + int(rows.max()) + 1], len(rows)


def measured_part_mask(mask: np.ndarray, entity: dict, world_map: np.ndarray) -> np.ndarray:
    """Associate a derived fixture part with its measured parent-mask subset.

    This is a geometric part of a SAM parent instance, not an independent
    semantic segmentation of the drawer or surface.
    """
    supported = np.isfinite(world_map).all(axis=-1) & (np.abs(world_map).sum(axis=-1) > 1e-6)
    supported &= ((world_map >= np.asarray(entity["lower"]) - .002)
                  & (world_map <= np.asarray(entity["upper"]) + .002)).all(axis=-1)
    return mask & supported


def render_marks(image_bytes: bytes, metadata: dict, entities: list[dict], *,
                 world_map: np.ndarray | None = None,
                 entity_masks: dict[str, np.ndarray] | None = None) -> tuple[bytes, dict]:
    """Draw public IDs using the identical projector in training and serving."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    if world_map is not None and world_map.shape != (image.height, image.width, 3):
        raise ValueError("RGB-D support and image dimensions differ")
    marks = []
    omitted = []
    for entity in entities:
        if not entity.get("visible", True):
            omitted.append({"id": entity["id"], "reason": "entity_not_currently_visible"})
            continue
        if entity_masks is not None and entity["id"] not in entity_masks:
            omitted.append({"id": entity["id"], "reason": "no_current_entity_mask_for_view"})
            continue
        box = project_bounds(entity, metadata, image.size)
        if box is None:
            continue
        projected_box = box
        count = None
        if world_map is not None:
            box, count = visible_box(box, entity, world_map,
                                     entity_masks[entity["id"]] if entity_masks is not None else None)
            if box is None:
                omitted.append({"id": entity["id"], "reason": "no_current_visible_depth_support",
                                "current_depth_points": count})
                continue
        draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), outline=(255, 216, 0), width=3)
        label = entity["id"]
        x, y = box[:2]
        text_box = draw.textbbox((x, y), label)
        draw.rectangle(text_box, fill=(0, 0, 0))
        draw.text((x, y), label, fill=(255, 216, 0))
        marks.append({"id": label, "box_xyxy": box, "source_step": entity.get("source_step"),
                      "src": entity.get("src", "perception"),
                      "projected_aabb_box_xyxy": projected_box, "current_depth_points": count})
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), {"version": VERSION, "width": image.width, "height": image.height,
                              "marks": marks, "omitted": omitted,
                              "image_sha256": hashlib.sha256(image_bytes).hexdigest()}


def render_pair(output: Path, step: int, artifacts: list[str], entities: list[dict],
                destination: Path, *, perception_evidence: dict | None = None) -> dict:
    """Read only explicitly registered frame artifacts and save both marks."""
    destination.mkdir(parents=True, exist_ok=True)
    views = []
    for view in VIEWS:
        image_name, calibration_name = f"{view}_high.png", f"{view}_metadata.json"
        world_name = f"{view}_world_high.npz"
        if any(name not in artifacts for name in (image_name, calibration_name, world_name)):
            raise ValueError(f"missing registered {view} decision image/calibration")
        import json
        image_path = output / image_name / f"{step:02d}.png"
        metadata_path = output / calibration_name / f"{step:02d}.json"
        metadata = json.loads(metadata_path.read_text())
        world_path = output / world_name / f"{step:02d}.npz"
        with np.load(world_path) as stored:
            world_map = stored["array"]
        entity_masks = {} if perception_evidence is not None else None
        mask_sources = {}
        for entity in entities if perception_evidence is not None else []:
            record = perception_evidence.get(entity["id"], {}).get("sam_mask_files", {}).get(view)
            if record is None and entity.get("part_of"):
                record = perception_evidence.get(entity["part_of"], {}).get("sam_mask_files", {}).get(view)
            if record is None or record["source_step"] != step:
                continue
            path = Path(record["path"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("registered SAM measurement mask changed")
            with np.load(path) as stored:
                mask = stored["array"].astype(bool)
            if mask.shape != world_map.shape[:2]:
                raise ValueError("registered SAM mask and current RGB-D dimensions differ")
            if entity.get("part_of"):
                # A drawer must not be scored against the entire cabinet mask.
                # Keep the original SAM instance as provenance and save only
                # its current RGB-D support for this measured part. This is the
                # same subset visible_box already uses to draw the rectangle.
                mask = measured_part_mask(mask, entity, world_map)
                part_path = destination / f"{view}_{entity['id']}_part_mask.npz"
                np.savez_compressed(part_path, array=mask)
                record = {
                    "path": str(part_path.resolve()),
                    "sha256": hashlib.sha256(part_path.read_bytes()).hexdigest(),
                    "camera": view, "source_step": step,
                    "source": "SAM_instance_subset_from_measured_part_geometry",
                    "parent_measurement_mask": record, "part_of": entity["part_of"],
                }
            entity_masks[entity["id"]] = mask
            mask_sources[entity["id"]] = record
        marked, detail = render_marks(image_path.read_bytes(), metadata, entities,
                                      world_map=world_map, entity_masks=entity_masks)
        marked_path = destination / f"{view}.png"
        marked_path.write_bytes(marked)
        views.append({"view": view, "path": str(marked_path.resolve()),
                      "sha256": hashlib.sha256(marked).hexdigest(),
                      "original_image": str(image_path), "calibration": str(metadata_path),
                      "current_depth_world": str(world_path),
                      "current_depth_world_sha256": hashlib.sha256(world_path.read_bytes()).hexdigest(),
                      "sam_measurement_masks": mask_sources,
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
