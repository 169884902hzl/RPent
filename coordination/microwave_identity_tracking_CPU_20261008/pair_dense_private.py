"""Private after-the-fact pairing; never used by public selection or stop."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(args):
    public = json.loads(args.public_summary.read_text())
    if public["private_labels_used"] is not False:
        raise ValueError("complete public-only summary must precede private pairing")
    audit = json.loads(args.public_audit.read_text())
    if reference(args.public_audit)["sha256"] not in {x["sha256"] for x in public["inputs"]}:
        raise ValueError("summary/audit hash differs")
    raw = json.loads(gzip.decompress(args.records.read_bytes()))
    frames = {row["capture_id"]: row for row in audit["rows"] if row["phase"] == "dense_control"}
    labels = {row["capture_id"]: row for row in raw["private_labels"]}
    if len(frames) != len(audit["rows"]) - 2 or len(labels) != len(raw["private_labels"]):
        raise ValueError("duplicate or missing explicit capture identity")
    if frames.keys() != labels.keys():
        raise ValueError("one separate private label per actual public control required")
    paired = []
    for capture, frame in frames.items():
        label = labels[capture]
        if frame["actual_control_index"] != label["actual_control_index"] or label["controls_execution"] is not False:
            raise ValueError("control identity or private isolation differs")
        truth = label.get("private_fixture_label") or {}
        paired.append({"capture_id": capture, "actual_control_index": frame["actual_control_index"],
            "private_close_truth": truth.get("satisfied"), "private_joint_qpos": truth.get("joint_qpos"),
            "actual_measured_door_cameras": frame["source_camera_distribution"],
            "temporal_stop_admitted": frame["stop_admitted"],
            "label_source": "simulation_diagnostic_only", "controls_execution": False,
            "train_allowed": False, "qualification": False})
    solved = [row for row in paired if row["private_close_truth"] is True]
    unknown = [row for row in paired if type(row["private_close_truth"]) is not bool]
    reverted = [(a["actual_control_index"], b["actual_control_index"]) for a, b in zip(paired, paired[1:])
        if a["private_close_truth"] is True and b["private_close_truth"] is False]
    episode = raw["episodes"][0]
    result = {"version": "microwave-dense-private-after-public-pairing/1-dev", "job": raw["job"],
        "inputs": [reference(path) for path in (args.public_summary, args.public_audit, args.records)],
        "paired_controls": len(paired), "unknown_private_controls": len(unknown),
        "true_close_controls": len(solved),
        "first_true_close_control": solved[0]["actual_control_index"] if solved else None,
        "last_private_close_truth": paired[-1]["private_close_truth"],
        "private_true_to_false_transitions": reverted,
        "true_close_control_frames_with_measured_door": sum(bool(row["actual_measured_door_cameras"]) for row in solved),
        "true_close_control_frames_without_measured_door": sum(not row["actual_measured_door_cameras"] for row in solved),
        "episode_wall_s": episode["wall_s"], "sacct": raw["sacct"],
        "raw_receipt_after_post_contact_recovery": episode["first_attempt"]["receipt"],
        "raw_server_chunk_execution": episode["server_chunk_execution"],
        "public_temporal_stop_count": public["runtime_stop_count"],
        "train_allowed": False, "qualification": False, "private_labels_control_execution": False,
        "paired": paired,
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("paired", "inputs")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-summary", type=Path, required=True)
    parser.add_argument("--public-audit", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
