# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Current public shell-front geometry supplies a SAM hint, never a door label."""

import base64
import io
import math

import numpy as np

from robots.libero.v5_microwave_door_temporal import MicrowaveDoorTemporalConfig
from robots.libero.v5_verification import vertical_face


VERSION = "microwave-current-public-shell-front-SAM-hint/1-dev"


def shell_front_panel_prompt(world, parent, fixed_anchor, *, source_step):
    """Prompt a front panel inside the shell when the external-panel hint misses.

    The fixed patch is independently measured while the door is open. Its
    bounds locate a current reference fit; no cached plane or inferred mask
    may become a door verdict. The caller must query SAM and retain the normal
    independent-mask, plane-consensus and temporal verification path.
    """
    from scipy.ndimage import distance_transform_edt, label

    config = MicrowaveDoorTemporalConfig()
    evidence = {"basis": VERSION, "source": "perception", "source_step": source_step,
                "trigger_only": True, "door_label_admitted": False, "stop_admitted": False,
                "panels": []}
    if (parent.name != "microwave" or not parent.visible or fixed_anchor is None
            or fixed_anchor.get("parent") != parent.id
            or type(fixed_anchor.get("source_step")) is not int
            or not 0 <= fixed_anchor["source_step"] <= source_step):
        return None, {**evidence, "reason": "independent_measured_shell_patch_missing"}
    world = np.asarray(world, dtype=float)
    if world.ndim != 3 or world.shape[-1] != 3:
        return None, {**evidence, "reason": "current_world_depth_invalid"}
    lo, hi = np.asarray(parent.lower), np.asarray(parent.upper)
    fixed_lo, fixed_hi = np.asarray(fixed_anchor["lower"]), np.asarray(fixed_anchor["upper"])
    valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    fixed = valid & ((world >= fixed_lo - .002) & (world <= fixed_hi + .002)).all(axis=-1)
    reference = vertical_face(world[fixed])
    if reference is None:
        return None, {**evidence, "reason": "current_fixed_front_patch_not_measured"}
    # Match existing fixed-patch selection and panel exclusion distances.
    normal = np.asarray(reference["normal_xy"])
    reference_distance = np.abs((world[..., :2] - reference["centre"][:2]) @ normal)
    static = ((world[..., :2] >= fixed_lo[:2] - .01)
              & (world[..., :2] <= fixed_hi[:2] + .01)).all(axis=-1)
    available = valid & ~static & (reference_distance <= config.maximum_plane_residual_m)
    available &= ((world >= lo - .015) & (world <= hi + .015)).all(axis=-1)
    available &= (world[..., 2] >= lo[2] + .01) & (world[..., 2] <= hi[2] - .01)
    evidence.update(current_fixed_reference=reference, fixed_patch_source_step=fixed_anchor["source_step"],
                    fixed_patch_pixels=int(fixed.sum()), candidate_pixels=int(available.sum()),
                    maximum_front_plane_distance_m=config.maximum_plane_residual_m)
    components, count = label(available)
    accepted = []
    for component in range(1, count + 1):
        mask = components == component
        if np.count_nonzero(mask) < 60:
            continue
        points = world[mask]
        fit = vertical_face(points)
        if fit is None:
            continue
        lower, upper = np.quantile(points, (.02, .98), axis=0)
        height = float(upper[2] - lower[2])
        angle = math.degrees(math.acos(float(np.clip(abs(normal @ fit["normal_xy"]), 0., 1.))))
        if height < .65 * (hi[2] - lo[2]) or angle > config.maximum_reference_angle_deg:
            continue
        accepted.append(mask)
        evidence["panels"].append({"plane": fit, "pixels": int(mask.sum()),
                                   "measured_height_m": height, "reference_angle_deg": angle})
    if len(accepted) != 1:
        return None, {**evidence, "reason": "current_shell_front_panel_missing_or_ambiguous"}
    point = list(map(int, np.unravel_index(np.argmax(distance_transform_edt(accepted[0])), available.shape)))
    rows, columns = np.where(accepted[0])
    roi = [int(rows.min()), int(columns.min()), int(rows.max()) + 1, int(columns.max()) + 1]
    return point, {**evidence, "point": point, "measured_panel_image_roi": roi,
                   "reason": "current_shell_front_point_for_SAM_only"}


def query_shell_front_panel(rpc, image_base64, point, guidance):
    """Query actual RGB in a measured ROI and map SAM's independent mask back.

    A full-image point query on job4508 selected the entire appliance, which
    correctly failed the original panel consensus. Keep those checks, and
    provide the visible front region rather than manufacturing a depth mask.
    """
    from PIL import Image
    from rpent.robots.components.sam3_client import Sam3Client

    with Image.open(io.BytesIO(base64.b64decode(image_base64, validate=True))) as source:
        image = source.convert("RGB")
    r0, c0, r1, c1 = guidance["measured_panel_image_roi"]
    # Retain a small visible RGB border; it is not a verifier tolerance.
    r0, c0, r1, c1 = max(0, r0 - 8), max(0, c0 - 8), min(image.height, r1 + 8), min(image.width, c1 + 8)
    cropped = image.crop((c0, r0, c1, r1))
    raw = io.BytesIO()
    cropped.save(raw, format="PNG")
    reply = rpc.call("sam3.segment", kwargs={"image_base64": base64.b64encode(raw.getvalue()).decode("ascii"),
        "point": [point[0] - r0, point[1] - c0], "min_score": .5}, timeout_s=120)
    guidance["SAM_crop_query"] = {"image_roi": [r0, c0, r1, c1], "padding_pixels": 8,
        "point_in_crop": [point[0] - r0, point[1] - c0], "found": reply.get("found"),
        "mask_source": "independent_SAM_on_actual_public_RGB_crop"}
    if not reply.get("found"):
        return reply
    mask = Sam3Client._decode_result(reply).mask
    if mask is None or mask.shape != (r1 - r0, c1 - c0):
        return {**reply, "found": False, "crop_reason": "independent_SAM_crop_mask_not_measured"}
    full = np.zeros((image.height, image.width), dtype=np.uint8)
    full[r0:r1, c0:c1] = mask.astype(np.uint8) * 255
    encoded = io.BytesIO()
    Image.fromarray(full).save(encoded, format="PNG")
    return {**reply, "mask_png_base64": base64.b64encode(encoded.getvalue()).decode("ascii"),
            "mask_shape": list(full.shape), "box": None}
