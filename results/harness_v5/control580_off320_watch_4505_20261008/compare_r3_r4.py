"""One-state budget diagnosis; stochastic prefixes are not causally paired."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def endpoints(case):
    rows = case["private_off_chunk_endpoints"]
    first = next((row for row in rows if row["turn_off"]), None)
    lost = [row for row in rows if first is not None
            and row["chunk"] > first["chunk"] and not row["turn_off"]]
    tail = rows[-10:]
    return {
        "job": case["job"],
        "off_block_endpoint_denominator": len(rows),
        "turn_off_true_block_endpoints": sum(row["turn_off"] for row in rows),
        "turn_off_true_first160_block_endpoints": sum(row["turn_off"] for row in rows[:160]),
        "turn_off_true_after160_block_endpoints": sum(row["turn_off"] for row in rows[160:]),
        "first_turn_off_block_endpoint": first,
        "false_after_first_true": len(lost),
        "first_false_after_first_true": lost[0] if lost else None,
        "final_block_endpoint": rows[-1],
        "last_ten_block_endpoints": tail,
        "joint_delta_last_ten_blocks_rad": tail[-1]["private_off_joint_qpos"][0][0] - tail[0]["private_off_joint_qpos"][0][0],
        "after_contact_release_retreat": [row for row in case["fixed_phase_labels"]
            if row["phase"] in ("after_contact", "after_release", "after_retreat")],
        "contact_controls": case["boundary"]["actual_contact_controls"],
        "per_control_truth_recorded": False,
    }


def main():
    before_path = ROOT.parent / "control580_r3_pair_watch_4495_20261008/report.json"
    after_path = ROOT / "report.json"
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())
    a, b = before["cases"][0], after["cases"][0]
    if a["state_sha256"] != b["state_sha256"] or a["episode"] != b["episode"]:
        raise ValueError("raw-state pairing changed")
    result = {
        "schema": "control580_r3_off160_r4_off320_one_state/1",
        "episode": b["episode"], "raw_state_sha256": b["state_sha256"],
        "same_registered_raw_state": True,
        "before_off160": endpoints(a), "after_off320": endpoints(b),
        "public_measurement_summary": {key: after["summary"][key] for key in (
            "temporal_public_frames", "public_view_records", "control_feature_records_present",
            "public_view_records_without_control_feature_query", "control_pose_measured_views",
            "directed_angle_measured_views", "endpoint_state_counts")},
        "inputs": [identity(before_path), identity(after_path)],
        "model_training": False, "stop_admitted": False, "freeze_evidence": False,
        "private_truth_controls_execution": False,
        "limits": [
            "One visited train state; no independent confirmation or population success claim.",
            "Different runs need not share pi0.5 sampled noise or intermediate on-phase actions.",
            "Private truth is at five-control block endpoints; no per-control success sequence.",
            "Longer budget executes all registered blocks even after a private endpoint is observed.",
            "Contact controls exclude 24 temporal hold controls and release/retreat scripted motion.",
        ],
    }
    path = ROOT / "paired_report.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("before_off160", "after_off320", "public_measurement_summary")}))


if __name__ == "__main__":
    main()
