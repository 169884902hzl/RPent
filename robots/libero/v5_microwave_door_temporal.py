# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Development-only microwave endpoints from public, time-separated RGB-D.

Callers provide explicit observations; this module reads no simulator state or
artifact directories. Plane records use ``vertical_face``'s existing fields.
Acquisition and physical qualification are separate from this prototype.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

import numpy as np

from robots.libero.v5_verification import vertical_face


VERSION = "microwave_door_temporal/1-dev"


@dataclass(frozen=True)
class MicrowaveDoorTemporalConfig:
    """Development thresholds, not a claim of confirmation-batch precision."""

    minimum_interval_s: float = .3
    maximum_mask_overlap: float = .05
    maximum_plane_residual_m: float = .008
    maximum_reference_angle_deg: float = 10.
    maximum_reference_drift_m: float = .01
    maximum_stable_angle_deg: float = 3.
    maximum_stable_displacement_m: float = .01
    open_minimum_angle_deg: float = 30.
    close_maximum_angle_deg: float = 15.


def _angle(a: np.ndarray, b: np.ndarray) -> float:
    # Eigenvector signs can flip between fits; a plane has no directed normal.
    return math.degrees(math.acos(float(np.clip(abs(a @ b), 0., 1.))))


def _plane(record: Mapping, observation: Mapping, config) -> tuple[dict | None, str | None]:
    """Validate one explicitly bound region, optionally fitting its raw cloud."""
    if (record.get("source", "perception") != "perception"
            or record.get("frame_id", "world") != "world"
            or record.get("length_unit", "m") != "m"):
        return None, "public_world_metres_provenance_missing"
    cameras = record.get("source_cameras", observation.get("source_cameras"))
    if (not isinstance(cameras, (list, tuple)) or not cameras
            or any(camera not in ("agentview", "wrist") for camera in cameras)):
        return None, "plane_source_camera_missing_or_invalid"
    if record.get("source_step", observation["source_step"]) != observation["source_step"]:
        return None, "plane_source_step_not_current"
    if "points_world" in record:
        try:
            cloud = np.asarray(record["points_world"], dtype=float)
        except (TypeError, ValueError):
            return None, "invalid_cloud"
        if cloud.ndim != 2 or cloud.shape[1] != 3:
            return None, "invalid_cloud_shape"
        fit = vertical_face(cloud)
        if fit is None:
            return None, "vertical_plane_fit_rejected"
    else:
        fit = record
    try:
        centre = np.asarray(fit["centre"], dtype=float)
        normal = np.asarray(fit["normal_xy"], dtype=float)
        residual = float(fit["residual_p90_m"])
        points = int(fit["points"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "invalid_plane_measurement"
    if (centre.shape != (3,) or normal.shape != (2,)
            or not np.isfinite(centre).all() or not np.isfinite(normal).all()
            or not math.isfinite(residual) or np.linalg.norm(normal) < 1e-6
            or not 0 <= residual <= config.maximum_plane_residual_m or points < 30):
        return None, "plane_measurement_not_supported"
    normal = normal / np.linalg.norm(normal)
    return {"centre": centre.tolist(), "normal_xy": normal.tolist(),
            "residual_p90_m": residual, "points": points,
            "source_step": observation["source_step"], "source_cameras": list(cameras),
            **{key: record[key] for key in ("path", "sha256", "mask_id") if key in record}}, None


def _observation(sample: Mapping, phase: str, index: int, config) -> tuple[dict | None, str | None]:
    if not isinstance(sample, Mapping):
        return None, "invalid_observation"
    if sample.get("source") != "perception" or sample.get("frame_id") != "world" or sample.get("length_unit") != "m":
        return None, "public_world_metres_provenance_missing"
    step = sample.get("source_step")
    if not isinstance(step, int) or isinstance(step, bool) or step < 0:
        return None, "source_step_missing_or_invalid"
    try:
        timestamp = float(sample["timestamp_s"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "timestamp_missing_or_invalid"
    if not math.isfinite(timestamp):
        return None, "timestamp_missing_or_invalid"
    if sample.get("arm_withdrawn") is not True or sample.get("occluded") is not False:
        return None, "unobstructed_after_withdrawal_not_measured"
    try:
        overlap = float(sample["frame_moving_mask_overlap"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, "independent_frame_and_door_masks_not_measured"
    if not math.isfinite(overlap) or not 0 <= overlap <= config.maximum_mask_overlap:
        return None, "frame_and_door_masks_overlap_or_invalid"
    planes = {}
    for kind in ("frame", "moving"):
        record = sample.get(kind)
        if not isinstance(record, Mapping):
            return None, f"{kind}_plane_not_measured"
        counts = sample.get("measurement_counts")
        counts = counts.get(kind) if isinstance(counts, Mapping) else None
        count = record.get("mask_count", counts.get("accepted_faces") if isinstance(counts, Mapping) else None)
        if type(count) is not int or count != 1:
            return None, f"{kind}_mask_missing_or_ambiguous"
        plane, reason = _plane(record, sample, config)
        if reason:
            return None, f"{kind}_{reason}"
        planes[kind] = plane
    for key in ("mask_id", "sha256", "path"):
        if key in planes["frame"] and planes["frame"][key] == planes["moving"].get(key):
            return None, "frame_and_door_share_same_measurement"
    relative = np.asarray(planes["moving"]["centre"]) - planes["frame"]["centre"]
    angle = _angle(np.asarray(planes["frame"]["normal_xy"]), np.asarray(planes["moving"]["normal_xy"]))
    return {"phase": phase, "index": index, "timestamp_s": timestamp, "source_step": step,
            "frame_moving_mask_overlap": overlap, **planes,
            "relative_centre_m": relative.tolist(),
            "relative_normal_gap_m": abs(float(relative[:2] @ np.asarray(planes["frame"]["normal_xy"]))),
            "relative_angle_deg": angle}, None


def measure_microwave_door_temporal(
    before_frames: Sequence[Mapping], after_frames: Sequence[Mapping], mode: str, *,
    config: MicrowaveDoorTemporalConfig | None = None,
    endpoint_stop_enabled: bool = False, endpoint_stop_qualified: bool = False,
) -> dict:
    """Measure a stable endpoint, retaining absent evidence as ``unmeasured``.

    Each phase needs at least two distinct, unobstructed captures spanning 0.3s.
    Observations declare perception/world/metres, capture step/time, withdrawal,
    cameras, unique mask counts and measured frame/door mask overlap. Each plane
    holds the existing fit or an explicit ``points_world`` array. Default stop
    admission is false; enabling it also requires independent physical
    qualification. This function never consumes qualification labels.
    """
    config = config or MicrowaveDoorTemporalConfig()
    evidence = {"version": VERSION, "source": "perception", "frame_id": "world",
                "length_unit": "m", "mode": mode, "config": asdict(config),
                "qualification": "external_physical_qualification_required",
                "endpoint_stop_enabled": endpoint_stop_enabled,
                "endpoint_stop_qualified": endpoint_stop_qualified,
                "endpoint_reached": None, "stop_admitted": False,
                "status": "unmeasured", "observations": []}

    def unknown(reason: str) -> dict:
        return {**evidence, "reason": reason}

    if mode not in ("open", "close"):
        return unknown("unsupported_microwave_mode")
    phases = {}
    for phase, frames in (("before", before_frames), ("after", after_frames)):
        if not isinstance(frames, Sequence) or isinstance(frames, (str, bytes)) or len(frames) < 2:
            return unknown(f"{phase}_requires_two_time_separated_frames")
        measured = []
        for index, sample in enumerate(frames):
            observation, reason = _observation(sample, phase, index, config)
            if reason:
                evidence["rejected_observation"] = {"phase": phase, "index": index}
                return unknown(reason)
            measured.append(observation)
            evidence["observations"].append(observation)
        if (any(b["timestamp_s"] <= a["timestamp_s"] or b["source_step"] <= a["source_step"]
                for a, b in zip(measured, measured[1:]))
                or measured[-1]["timestamp_s"] - measured[0]["timestamp_s"] < config.minimum_interval_s - 1e-9):
            return unknown(f"{phase}_captures_not_distinct_and_time_separated")
        phases[phase] = measured
    if (phases["after"][0]["timestamp_s"] <= phases["before"][-1]["timestamp_s"]
            or phases["after"][0]["source_step"] <= phases["before"][-1]["source_step"]):
        return unknown("after_not_newer_than_before")

    anchor = phases["before"][0]["frame"]
    normal = np.asarray(anchor["normal_xy"])
    reference_angles = [_angle(normal, np.asarray(row["frame"]["normal_xy"]))
                        for row in evidence["observations"]]
    reference_drifts = [abs(float((np.asarray(row["frame"]["centre"][:2])
                                  - anchor["centre"][:2]) @ normal))
                        for row in evidence["observations"]]
    evidence["reference_stability"] = {"maximum_angle_deg": max(reference_angles),
                                        "maximum_normal_drift_m": max(reference_drifts)}
    if (max(reference_angles) > config.maximum_reference_angle_deg
            or max(reference_drifts) > config.maximum_reference_drift_m):
        return unknown("independent_fixed_frame_not_stable")

    summaries = {}
    for phase, rows in phases.items():
        angles = np.asarray([row["relative_angle_deg"] for row in rows])
        centres = np.asarray([row["relative_centre_m"] for row in rows])
        displacement = float(np.linalg.norm(centres[:, None] - centres, axis=-1).max())
        summaries[phase] = {"angle_median_deg": float(np.median(angles)),
                            "angle_range_deg": float(np.ptp(angles)),
                            "relative_centre_median_m": np.median(centres, axis=0).tolist(),
                            "maximum_relative_centre_displacement_m": displacement}
        evidence["phases"] = summaries
        if (np.ptp(angles) > config.maximum_stable_angle_deg
                or displacement > config.maximum_stable_displacement_m):
            return unknown(f"{phase}_door_not_stable")
    angles = [row["relative_angle_deg"] for row in phases["after"]]
    endpoint = all(angle >= config.open_minimum_angle_deg for angle in angles) if mode == "open" else all(
        angle <= config.close_maximum_angle_deg for angle in angles)
    change = summaries["after"]["angle_median_deg"] - summaries["before"]["angle_median_deg"]
    evidence.update(status="measured", reason="stable_endpoint" if endpoint else "stable_non_endpoint",
                    endpoint_reached=bool(endpoint), angle_change_deg=change,
                    relative_centre_change_m=(np.asarray(summaries["after"]["relative_centre_median_m"])
                                              - summaries["before"]["relative_centre_median_m"]).tolist(),
                    requested_direction_observed=bool(change >= config.maximum_stable_angle_deg if mode == "open"
                                                      else change <= -config.maximum_stable_angle_deg),
                    stop_admitted=bool(endpoint and endpoint_stop_enabled and endpoint_stop_qualified))
    return evidence
