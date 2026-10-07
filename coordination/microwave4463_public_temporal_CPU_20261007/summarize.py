"""Summarize the explicit job4463 public records without replacing verdicts."""

import collections
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from robots.libero.v5_microwave_door_temporal import measure_microwave_capture_pair


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "public_records_v2.json"


def main():
    data = json.loads(INPUT.read_text())
    rows = []
    counts = collections.defaultdict(collections.Counter)
    for record in data["records"]:
        frames = []
        for frame in record["frames"]:
            per_view = {}
            for camera, view in frame["views"].items():
                measured = view["measurement_counts"]
                for kind in ("frame", "moving"):
                    counts[camera][kind + "_sam_instances"] += measured[kind]["sam_instances"]
                    counts[camera][kind + "_plane_available"] += view[kind] is not None
                    counts[camera][kind + "_outside_parent"] += measured[kind]["outside_parent"]
                fixed = view.get("fixed_frame_geometry") or {}
                counts[camera]["frames"] += 1
                counts[camera]["fixed_geometry:" + fixed.get("reason", "accepted")] += 1
                per_view[camera] = {
                    "frame_plane_available": view["frame"] is not None,
                    "door_plane_available": view["moving"] is not None,
                    "frame_sam_instances": measured["frame"]["sam_instances"],
                    "door_sam_instances": measured["moving"]["sam_instances"],
                    "door_outside_parent": measured["moving"]["outside_parent"],
                    "fixed_geometry_reason": fixed.get("reason"),
                    "panel_filter_reasons": [entry.get("reason") for entry in
                                             measured["moving"].get("panel_filters", [])],
                    "robot_masks": frame["robot_mask_evidence"][camera]["robot_masks"],
                }
            fixed, moving = frame["frame"], frame["moving"]
            angle = None
            if fixed and moving:
                dot = abs(np.asarray(fixed["normal_xy"]) @ np.asarray(moving["normal_xy"]))
                angle = math.degrees(math.acos(float(np.clip(dot, 0, 1))))
            frames.append({
                "source_step": frame["source_step"], "source_cameras": frame["source_cameras"],
                "arm_withdrawn": frame["arm_withdrawn"], "occluded": frame["occluded"],
                "relative_angle_deg": angle, "frame_moving_mask_overlap": frame["frame_moving_mask_overlap"],
                "fixed_residual_p90_m": (fixed or {}).get("residual_p90_m"),
                "door_residual_p90_m": (moving or {}).get("residual_p90_m"),
                "frame_mask_id": (fixed or {}).get("mask_id"), "door_mask_id": (moving or {}).get("mask_id"),
                "per_view": per_view,
            })
        original = record.get("measurement") or {}
        readiness = measure_microwave_capture_pair(record["frames"], phase=record["phase"])
        rows.append({
            "index": record["index"], "phase": record["phase"], "chunks": record["chunks"],
            "original_verdict": {key: original.get(key) for key in
                                 ("status", "reason", "endpoint_reached", "stop_admitted", "rejected_observation")},
            "offline_pair_readiness_only": {key: readiness.get(key) for key in
                                            ("status", "reason", "rejected_observation")},
            "frames": frames,
        })
    summary = {
        "version": "microwave4463-public-temporal-diagnosis/1-dev", "job": 4463,
        "source": data["source"], "training_allowed": False,
        "freeze_evidence": False, "confirmation": False,
        "raw_public_file": {"path": str(INPUT), "sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest()},
        "records": rows, "views": dict(counts),
        "root_cause": "All after verdicts reject before index1/source_step21: zero observed robot masks leave occluded=null.",
        "not_root_cause": "Agentview has valid independent fixed and moving plane measurements in all18 captures.",
        "behavioral_fix": "Retry up to3 total fresh public baseline pairs before contact, with6 actual neutral holds per pair; never infer clearance from zero masks.",
        "physical_fix_verified": False,
    }
    (ROOT / "diagnosis_v2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"records": len(rows), "views": summary["views"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
