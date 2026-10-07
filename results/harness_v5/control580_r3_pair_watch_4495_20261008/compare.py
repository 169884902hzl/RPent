"""Pair two visited diagnostic runs on the same registered raw-state hash."""

from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def endpoints(case):
    rows = case["private_off_chunk_endpoints"]
    true = [row for row in rows if row["turn_off"] is True]
    first = true[0] if true else None
    back = [row for row in rows if first and row["chunk"] > first["chunk"] and row["turn_off"] is False]
    phases = {row["phase"]: row for row in case["fixed_phase_labels"]}
    return {"sampled_block_endpoints": len(rows), "turn_off_true": len(true),
            "first_turn_off_endpoint": first, "false_after_first_true": len(back),
            "first_retreat_from_endpoint": back[0] if back else None,
            "last_block_endpoint": rows[-1], "joint_qpos_range": case["private_joint_qpos_range"],
            "after_contact": phases.get("after_contact"), "after_release": phases.get("after_release"),
            "after_retreat": phases.get("after_retreat"), "sample_unit": "five_control_block_endpoint",
            "per_control_truth_saved": False}


def main():
    out = Path(__file__).resolve().parent
    old_path = out.parent / "control580_three_train_states_watch_20261008/report.json"
    new_path = out / "report.json"
    old, new = json.loads(old_path.read_text()), json.loads(new_path.read_text())
    before = next(c for c in old["cases"] if c["job"] == 4467 and c["part"] == 0)
    after = new["cases"][0]
    if before["state_sha256"] != after["state_sha256"] or before["episode"] != after["episode"]:
        raise ValueError("raw initial state does not match; pairing is invalid")
    views = [v for frame in new["temporal_frames"] for v in frame["views"].values()]
    queried = [v for v in views if v["control_feature_record_present"]]
    report = {"schema": "control580_r2_r3_same_state_pair/1", "episode": after["episode"],
        "state_sha256": after["state_sha256"], "same_registered_raw_state": True,
        "before": {"job": 4467, "variant": "r2_release_retreat_before_off", **endpoints(before)},
        "after": {"job": 4495, "variant": "r3_skip_release_retreat_before_off", **endpoints(after)},
        "public_control_features": {"temporal_frames": len(new["temporal_frames"]),
            "view_records": len(views), "queried_view_records": len(queried),
            "control_pose_measured": sum(v["control_pose_measured"] for v in queried),
            "directed_angle_measured": sum(v["directed_angle_measured"] for v in queried),
            "queried_reasons": dict(Counter(v["reason"] for v in queried)),
            "queried_endpoint_states": dict(Counter(v["endpoint_state"] for v in queried)),
            "raw_frames_without_query": len(views) - len(queried),
            "public_contact_sensor_available": False, "arm_withdrawn_visibility_verified": False},
        "source_files": new["source_files"], "inputs": [ref(old_path), ref(new_path)],
        "stop_admitted": False, "training_performed": False, "freeze_evidence": False,
        "limits": ["One visited original state; no independent confirmation or population success claim.",
            "Truth is measured at block endpoints, not at every individual control.",
            "Skipping release/retreat preserves the commanded posture; physical contact is not publicly verified.",
            "Intentionally unqueried raw frames are retained for offline analysis and do not count as SAM failures."]}
    path = out / "paired_report.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"before": report["before"], "after": report["after"],
                      "public_control_features": report["public_control_features"]}))


if __name__ == "__main__":
    main()
