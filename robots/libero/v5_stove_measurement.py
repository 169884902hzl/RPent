# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Development stove endpoint evidence from calibrated RGB-D measurements.

The original-task RGB examples selected these development features; they do
not qualify a verifier. Independent on/off confirmation is still required.
Support samples are audit evidence, not planner-state or receipt text. For a
static stove, the caller should reuse the pre-action measured bounds in the
after measurement to avoid changing the region when segmentation changes.
"""

from dataclasses import asdict, dataclass
import math

import numpy as np


VERSION = "measured_stove_rgbd/4-off-endpoint-unmeasured-dev"
MAIN_CAMERAS = frozenset(("agentview", "main", "agentview_high"))


@dataclass(frozen=True)
class StoveDevelopmentParameters:
    """Registered development parameters, not validated success thresholds."""

    xy_margin_m: float = .01
    color_support_band_m: float = .006
    sample_lower_margin_m: float = .02
    sample_upper_margin_m: float = .30
    minimum_surface_pixels: int = 100
    minimum_red_pixels: int = 10
    minimum_red_fraction_on: float = .02
    minimum_red_anchors: int = 8
    maximum_red_anchors: int = 64
    support_distance_m: float = .006
    support_height_tolerance_m: float = .002
    minimum_reference_coverage_off: float = .95
    maximum_reference_red_fraction_off: float = .05
    maximum_surface_red_fraction_off: float = .01
    maximum_stable_red_fraction_change: float = .005
    minimum_stable_interval_s: float = .3
    red_channel_minimum: int = 120
    red_channel_ratio: float = 1.4
    red_channel_margin: int = 40
    sample_grid_resolution: int = 128


DEFAULT_PARAMETERS = StoveDevelopmentParameters()


def _entity_field(entity, key):
    return entity[key] if isinstance(entity, dict) else getattr(entity, key)


def measure_stove_rgbd(image, world, entity, source_step, camera,
                       *, parameters=DEFAULT_PARAMETERS) -> dict:
    """Measure red supported pixels; absence of red alone cannot establish off.

    Pixel indices stay on a deterministic image grid so fixed-main-camera
    before/after samples can test whether the known red coil support remains
    visible. XYZ comes solely from the supplied calibrated depth map.
    """
    image, world = np.asarray(image), np.asarray(world, dtype=float)
    if image.ndim != 3 or image.shape[2] < 3 or world.shape != (*image.shape[:2], 3):
        raise ValueError("stove RGB-D images must have matching HxW dimensions")
    rgb = image[..., :3].astype(float)
    if not np.isfinite(rgb).all() or np.any(rgb < 0) or np.any(rgb > 255):
        raise ValueError("stove RGB must contain finite 8-bit-range values")
    # A floating [0,1] image has a different intensity contract.
    if np.issubdtype(image.dtype, np.floating) and rgb.max(initial=0) <= 1:
        raise ValueError("stove RGB expects the 0..255 intensity scale")
    lower = np.asarray(_entity_field(entity, "lower"), dtype=float)
    upper = np.asarray(_entity_field(entity, "upper"), dtype=float)
    if lower.shape != (3,) or upper.shape != (3,) or not np.isfinite([lower, upper]).all() or np.any(lower > upper):
        raise ValueError("stove bounds must be finite measured XYZ bounds")
    if not isinstance(source_step, (int, np.integer)) or source_step < 0:
        raise ValueError("stove source_step must identify the recorded measurement")
    valid = np.isfinite(world).all(axis=-1) & (np.abs(world).sum(axis=-1) > 1e-6)
    xy = valid & ((world[..., :2] >= lower[:2]-parameters.xy_margin_m)
                  & (world[..., :2] <= upper[:2]+parameters.xy_margin_m)).all(axis=-1)
    surface = xy & (np.abs(world[..., 2]-upper[2]) <= parameters.color_support_band_m)
    red = (rgb[..., 0] >= parameters.red_channel_minimum)
    red &= rgb[..., 0] >= parameters.red_channel_ratio*rgb[..., 1]
    red &= rgb[..., 0] >= parameters.red_channel_ratio*rgb[..., 2]
    red &= rgb[..., 0]-np.maximum(rgb[..., 1], rgb[..., 2]) >= parameters.red_channel_margin
    surface_count = int(surface.sum())
    red_count = int((surface & red).sum())
    red_fraction = red_count/surface_count if surface_count else None
    visible = bool(_entity_field(entity, "visible") and surface_count >= parameters.minimum_surface_pixels)
    stride = max(1, math.ceil(max(image.shape[:2])/parameters.sample_grid_resolution))
    rows, cols = np.indices(image.shape[:2])
    grid = (rows % stride == 0) & (cols % stride == 0)
    sampled = grid & xy & (world[..., 2] >= lower[2]-parameters.sample_lower_margin_m)
    sampled &= world[..., 2] <= upper[2]+parameters.sample_upper_margin_m
    samples = [[int(r), int(c), *[round(float(v), 6) for v in world[r, c]], bool(surface[r, c] and red[r, c])]
               for r, c in zip(*np.where(sampled))]
    anchors = [sample for sample in samples if sample[-1]]
    if len(anchors) > parameters.maximum_red_anchors:
        indices = np.linspace(0, len(anchors)-1, parameters.maximum_red_anchors, dtype=int)
        anchors = [anchors[i] for i in indices]
    on = bool(visible and red_count >= parameters.minimum_red_pixels
              and red_fraction >= parameters.minimum_red_fraction_on
              and len(anchors) >= parameters.minimum_red_anchors)
    return {"version": VERSION, "src": "perception", "source_step": int(source_step),
            "camera": str(camera), "image_shape": list(image.shape[:2]), "sample_stride": stride,
            "entity": str(_entity_field(entity, "id")), "visible": visible,
            "measured_bounds": {"lower": lower.tolist(), "upper": upper.tolist()},
            "features": {"surface_pixels": surface_count, "red_pixels": red_count,
                         "red_fraction": red_fraction, "red_anchor_count": len(anchors)},
            "state": "on" if on else "unmeasured",
            "reason": "red_coil_support_measured" if on else "surface_not_sufficiently_visible" if not visible
                      else "red_absence_requires_visible_known_on_reference",
            "red_support_anchors": anchors, "support_samples": samples,
            "surface_region": {"shape": list(surface.shape), "encoding": "numpy_packbits_big_hex",
                               "mask": np.packbits(surface.reshape(-1)).tobytes().hex()},
            "development_parameters": asdict(parameters)}


def _compact(measurement):
    if not measurement:
        return None
    return {key: measurement.get(key) for key in
            ("version", "src", "source_step", "camera", "image_shape", "entity", "visible", "features", "state", "reason")}


def measured_stove_endpoint(before, after, mode, *, second_after=None, interval_s=None,
                            parameters=DEFAULT_PARAMETERS):
    """Return requested-state evidence; ambiguous/occluded states are unmeasured.

    On has positive visible-red evidence. A dark transition requires a main
    view and a previously measured on-reference: at least 95% of its sampled
    red support must remain at the same depth and no sampled support may be
    detectably occluded. It additionally requires two stable new frames
    separated by 0.3 seconds with complete visibility of the same previously
    measured surface region. This is an on-to-dark visual transition, not a
    control endpoint. Without independent measured control-endpoint evidence,
    even two fully visible dark frames leave the requested off state unmeasured.
    """
    if mode not in ("turn_on", "turn_off"):
        raise ValueError("stove endpoint only supports turn_on/turn_off")
    evidence = {"verification_rule": VERSION, "requested_mode": mode, "state": "unmeasured",
                "before": _compact(before), "after": _compact(after),
                "development_parameters": asdict(parameters)}

    def unknown(reason):
        return None, {**evidence, "reason": reason}

    if not after or not after.get("visible") or after.get("src") != "perception":
        return unknown("current_stove_surface_not_measured")
    if before and after.get("source_step", -1) <= before.get("source_step", -1):
        return unknown("no_distinct_after_measurement")
    if after.get("state") == "on":
        return mode == "turn_on", {**evidence, "state": "on", "reason": "visible_red_coil_support"}
    if after.get("camera") not in MAIN_CAMERAS:
        return unknown("off_requires_main_view")
    if not before or before.get("state") != "on" or before.get("src") != "perception":
        return unknown("off_requires_known_on_reference")
    if before.get("entity") != after.get("entity"):
        return unknown("known_on_reference_is_different_entity")
    if before.get("camera") != after.get("camera") or before.get("image_shape") != after.get("image_shape"):
        return unknown("reference_camera_or_geometry_changed")
    anchors = before.get("red_support_anchors", [])
    if len(anchors) < parameters.minimum_red_anchors:
        return unknown("known_on_support_insufficient")
    current = {(sample[0], sample[1]): sample for sample in after.get("support_samples", [])}
    matched, still_red, missing, changed = 0, 0, 0, 0
    for anchor in anchors:
        sample = current.get((anchor[0], anchor[1]))
        if sample is None:
            missing += 1
        elif (math.dist(anchor[2:5], sample[2:5]) > parameters.support_distance_m
              or abs(anchor[4]-sample[4]) > parameters.support_height_tolerance_m):
            changed += 1
        else:
            matched += 1
            still_red += bool(sample[-1])
    coverage = matched/len(anchors)
    red_retention = still_red/matched if matched else None
    evidence["reference_support"] = {"anchors": len(anchors), "matched": matched,
        "missing": missing, "changed_or_occluded": changed, "coverage": coverage,
        "red_fraction": red_retention, "support_distance_m": parameters.support_distance_m,
        "support_height_tolerance_m": parameters.support_height_tolerance_m}
    if changed or coverage < parameters.minimum_reference_coverage_off:
        return unknown("known_on_support_occluded_or_unmeasured")
    if red_retention > parameters.maximum_reference_red_fraction_off:
        return unknown("known_on_red_support_not_clearly_off")
    evidence["observed_coil_state"] = "dark"
    if second_after is None:
        return unknown("dark_coils_do_not_measure_control_off_endpoint")
    if interval_s is None or not math.isfinite(interval_s) or interval_s < parameters.minimum_stable_interval_s:
        return unknown("off_requires_separated_stable_frames")
    if (not second_after.get("visible") or second_after.get("src") != "perception"
            or second_after.get("source_step", -1) <= after.get("source_step", -1)):
        return unknown("off_second_frame_not_new_or_visible")
    if (second_after.get("entity") != before.get("entity")
            or second_after.get("camera") != before.get("camera")
            or second_after.get("image_shape") != before.get("image_shape")):
        return unknown("off_second_frame_geometry_changed")
    evidence.update(second_after=_compact(second_after), measurement_interval_s=float(interval_s),
                    measurement_scope="visible_stove_on_to_dark_transition_not_joint_endpoint")
    if second_after.get("state") == "on":
        return False, {**evidence, "state": "on", "reason": "red_returned_in_second_frame"}
    # Apply the same on-reference depth/visibility audit to the second frame;
    # that single dark observation still cannot establish off by itself.
    _, second = measured_stove_endpoint(before, second_after, "turn_off", parameters=parameters)
    evidence["second_reference_support"] = second.get("reference_support")
    if second.get("reason") != "dark_coils_do_not_measure_control_off_endpoint":
        return unknown("off_second_frame_" + second["reason"])
    fractions = [sample.get("features", {}).get("red_fraction") for sample in (after, second_after)]
    if any(value is None or value > parameters.maximum_surface_red_fraction_off for value in fractions):
        return unknown("surface_red_fraction_not_clearly_off")
    if abs(fractions[0] - fractions[1]) > parameters.maximum_stable_red_fraction_change:
        return unknown("off_red_fraction_not_stable")
    regions = [sample.get("surface_region") for sample in (before, after, second_after)]
    if any(not region or region.get("encoding") != "numpy_packbits_big_hex" for region in regions):
        return unknown("complete_surface_region_not_recorded")
    masks = []
    for region in regions:
        if region["shape"] != before["image_shape"]:
            return unknown("surface_region_geometry_changed")
        count = int(np.prod(region["shape"]))
        packed = np.frombuffer(bytes.fromhex(region["mask"]), dtype=np.uint8)
        if len(packed) != math.ceil(count / 8):
            return unknown("surface_region_mask_invalid")
        masks.append(np.unpackbits(packed)[:count].astype(bool))
    reference_count = int(masks[0].sum())
    if reference_count < parameters.minimum_surface_pixels:
        return unknown("known_on_surface_region_insufficient")
    coverages = [int(np.count_nonzero(mask & masks[0])) / reference_count for mask in masks[1:]]
    evidence["complete_region_visibility"] = {"reference_pixels": reference_count,
                                              "first_coverage": coverages[0], "second_coverage": coverages[1]}
    if any(coverage != 1. for coverage in coverages):
        return unknown("known_on_surface_region_occluded_or_unmeasured")
    evidence["visual_transition"] = "known_on_surface_fully_visible_and_stably_dark_in_two_frames"
    return unknown("stable_dark_coils_do_not_measure_control_off_endpoint")
