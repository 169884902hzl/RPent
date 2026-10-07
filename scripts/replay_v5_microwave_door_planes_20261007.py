#!/usr/bin/env python3
"""Offline replay of saved microwave door/frame point-cloud plane fits.

This utility consumes the public measurement references already recorded by a
microwave probe.  It loads each saved ``*.npz`` cloud, re-runs the existing
``vertical_face`` fitter, checks its recorded SHA, and reports the endpoint
angle that the existing verifier would see when both a frame and moving face
are available.  It performs no SAM calls, simulator reset, robot action, or
goal/private-label lookup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from robots.libero.v5_verification import vertical_face


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_path(raw: str, replacements: list[tuple[str, str]]) -> Path:
    """Resolve a recorded path, optionally replacing a remote root prefix."""
    for old, new in replacements:
        if raw == old or raw.startswith(old.rstrip("/") + "/"):
            return Path(new + raw[len(old):])
    return Path(raw)


def load_cloud(ref: dict, replacements: list[tuple[str, str]]) -> tuple[np.ndarray | None, dict]:
    raw = ref.get("path")
    if not isinstance(raw, str):
        return None, {"status": "missing_path"}
    path = resolve_path(raw, replacements)
    detail = {"recorded_path": raw, "resolved_path": str(path),
              "recorded_sha256": ref.get("sha256")}
    if not path.is_file():
        return None, {**detail, "status": "missing_file"}
    digest = sha256(path)
    detail["resolved_sha256"] = digest
    if ref.get("sha256") and digest != ref["sha256"]:
        return None, {**detail, "status": "sha256_mismatch"}
    try:
        with np.load(path) as data:
            if not data.files:
                return None, {**detail, "status": "empty_npz"}
            cloud = np.asarray(data[data.files[0]], dtype=float)
    except Exception as exc:  # keep one bad artifact visible in the report
        return None, {**detail, "status": "npz_read_error", "error": repr(exc)}
    if cloud.ndim != 2 or cloud.shape[1] != 3:
        return None, {**detail, "status": "invalid_cloud_shape", "shape": list(cloud.shape)}
    return cloud, {**detail, "status": "loaded", "points": int(len(cloud))}


def fit_match(recorded: dict, fitted: dict | None) -> dict:
    if fitted is None:
        return {"status": "fit_rejected"}
    expected = {key: recorded.get(key) for key in ("centre", "normal_xy", "residual_p90_m", "points")}
    normal_cosine = None
    if expected["normal_xy"] is not None:
        a = np.asarray(expected["normal_xy"], dtype=float)
        b = np.asarray(fitted["normal_xy"], dtype=float)
        if np.linalg.norm(a) and np.linalg.norm(b):
            normal_cosine = float(abs(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    centre_error = None
    if expected["centre"] is not None:
        centre_error = float(np.linalg.norm(np.asarray(expected["centre"], dtype=float)
                                            - np.asarray(fitted["centre"], dtype=float)))
    residual_error = None
    if expected["residual_p90_m"] is not None:
        residual_error = float(abs(float(expected["residual_p90_m"])
                                  - float(fitted["residual_p90_m"])))
    return {"status": "fit_accepted", "recorded": expected, "replayed": fitted,
            "normal_cosine_abs": normal_cosine, "centre_error_m": centre_error,
            "residual_error_m": residual_error,
            "point_count_match": expected["points"] in (None, fitted["points"]),
            "normal_match_1e-6": normal_cosine is None or normal_cosine >= 1 - 1e-6,
            "centre_match_1e-6_m": centre_error is None or centre_error <= 1e-6,
            "residual_match_1e-9_m": residual_error is None or residual_error <= 1e-9}


def endpoint_angle(frame: dict, moving: dict) -> float | None:
    if not frame or not moving or frame.get("normal_xy") is None or moving.get("normal_xy") is None:
        return None
    a = np.asarray(frame["normal_xy"], dtype=float)
    b = np.asarray(moving["normal_xy"], dtype=float)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return None
    return float(math.degrees(math.acos(float(np.clip(abs(a @ b)
                                                       / (np.linalg.norm(a) * np.linalg.norm(b)), 0, 1)))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--path-prefix", action="append", default=[], metavar="OLD=NEW",
                        help="replace a recorded artifact prefix, repeatable")
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    replacements = []
    for item in args.path_prefix:
        if "=" not in item:
            raise ValueError(f"invalid --path-prefix {item!r}; expected OLD=NEW")
        old, new = item.split("=", 1)
        replacements.append((old, new))

    cases, artifact_rows = [], []
    status_counts = {}
    ref_count = loaded_count = 0
    for record in report.get("records", []):
        measurement = record.get("public_measurements") or {}
        phases = {}
        for phase in ("before", "after"):
            current = measurement.get(phase) or {}
            phase_out = {"source_step": current.get("source_step"), "frame": None, "moving": None}
            fits = {}
            for kind in ("frame", "moving"):
                ref = current.get(kind)
                if not isinstance(ref, dict):
                    continue
                ref_count += 1
                cloud, load = load_cloud(ref, replacements)
                status_counts[load["status"]] = status_counts.get(load["status"], 0) + 1
                row = {"kind": kind, "load": load}
                if cloud is not None:
                    loaded_count += 1
                    row["fit"] = fit_match(ref, vertical_face(cloud))
                    fits[kind] = row["fit"].get("replayed")
                phase_out[kind] = row
                artifact_rows.append({"case": record.get("case"), "phase": phase,
                                      "kind": kind, **row})
            angle = endpoint_angle(fits.get("frame"), fits.get("moving"))
            phase_out["replayed_endpoint_angle_deg"] = angle
            if angle is not None:
                phase_out["open_threshold_pass"] = bool(angle >= 30)
                phase_out["close_threshold_pass"] = bool(angle <= 15)
            phases[phase] = phase_out
        cases.append({"case": record.get("case"), "type": record.get("type"),
                      "classification": record.get("classification"), "phases": phases})

    fit_rows = [row["fit"] for row in artifact_rows if "fit" in row]
    accepted_rows = [row for row in fit_rows if row.get("status") == "fit_accepted"]
    output = {"version": "offline-microwave-door-plane-replay/1",
              "input_report": str(args.report.resolve()),
              "scope": "saved public RGB-D clouds only; no SAM/simulator/action/private labels",
              "path_prefixes": [{"old": old, "new": new} for old, new in replacements],
              "registered_cases": len(report.get("records", [])),
              "artifact_references": ref_count, "artifacts_loaded": loaded_count,
              "artifact_status_counts": status_counts,
              "fit_acceptance": {"accepted": sum(item.get("status") == "fit_accepted" for item in fit_rows),
                                  "rejected": sum(item.get("status") == "fit_rejected" for item in fit_rows),
                                  "recorded_replay_exact": sum(item.get("normal_match_1e-6", False)
                                                               and item.get("centre_match_1e-6_m", False)
                                                               and item.get("residual_match_1e-9_m", False)
                                                               and item.get("point_count_match", False)
                                                               for item in accepted_rows)},
              "cases": cases,
              "artifacts": artifact_rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "cases": len(cases),
                      "artifact_references": ref_count, "artifacts_loaded": loaded_count,
                      "artifact_status_counts": status_counts}, sort_keys=True))


if __name__ == "__main__":
    main()
