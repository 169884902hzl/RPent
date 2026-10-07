"""Join explicit dense public inputs to same-state independently observed masks.

Re-seeding is allowed only when the current RGB and depth exactly equal the
registered runtime frame. No private labels or model results are consulted.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def checked(record):
    path = Path(record["path"])
    if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("explicit public artifact differs: " + str(path))
    return path


def array(record):
    with np.load(checked(record), allow_pickle=False) as saved:
        if len(saved.files) != 1:
            raise ValueError("one public depth array required")
        return saved[saved.files[0]]


def pixels(record):
    return np.asarray(Image.open(checked(record)).convert("RGB"))


def build(args):
    source = json.loads(args.public.read_text())
    if source["private_labels_included"] is not False:
        raise ValueError("separate public-only input required")
    original = source["runtime_public_records"]
    if not original or original[0]["phase"] != "before":
        raise ValueError("completed runtime baseline and explicit first independent door required")
    rows = []
    baseline = original[0]["frames"]
    for frame in baseline:
        view = frame["views"]["agentview"]
        rows.append({"phase": "before", "block": None, "source_step": frame["source_step"],
            "capture_id": "runtime-baseline:" + str(frame["source_step"]),
            "artifacts": frame["artifacts"]["agentview"], "moving": view.get("moving"),
            "wrist_artifacts": frame["artifacts"]["wrist"],
            "fixed": view.get("frame"),
            "robot_mask": frame.get("robot_mask_evidence", {}).get("agentview", {}).get("robot_mask_artifact")})
    first_fixed = baseline[0]["views"]["agentview"]["frame"]
    fixed_cloud = array(first_fixed)
    lo, hi = np.quantile(fixed_cloud, (.02, .98), axis=0)
    anchor = {"lower": lo.tolist(), "upper": hi.tolist(), "source_step": baseline[0]["source_step"]}
    probes = {record["chunks"]: record["frames"][0] for record in original if record["phase"] == "probe"}
    parity = []
    captures = source["public_records"]
    server_ids = {row["capture_id"].split(":")[0] for row in captures}
    if len(server_ids) != 1:
        raise ValueError("infrastructure restart requires separate explicit identity trajectories")
    counts = [row["actual_control_index"] for row in captures]
    if counts != list(range(1, len(counts) + 1)):
        raise ValueError("actual control frame sequence is not contiguous")
    for capture in captures:
        control = capture["actual_control_index"]
        if capture.get("capture_error"):
            raise ValueError("capture failure: preserve it separately, no missing frame bridge")
        row = {"phase": "dense_control", "block": control / 5, "source_step": None,
            "actual_control_index": control, "capture_id": capture["capture_id"],
            "artifacts": capture["views"]["agentview"], "moving": None, "fixed": None,
            "wrist_artifacts": capture["views"]["wrist"],
            "robot_mask": None, "proprioception": capture["robot"]}
        if control % 5 == 0 and control // 5 in probes:
            original_frame = probes[control // 5]
            prior = original_frame["artifacts"]["agentview"]
            image_equal = np.array_equal(pixels(row["artifacts"]["rgb"]), pixels(prior["rgb"]))
            depth_equal = np.array_equal(array(row["artifacts"]["world"]), array(prior["world"]))
            parity.append({"actual_control_index": control, "runtime_source_step": original_frame["source_step"],
                           "RGB_pixels_equal": bool(image_equal), "world_depth_equal": bool(depth_equal)})
            if image_equal and depth_equal:
                view = original_frame["views"]["agentview"]
                row.update(moving=view.get("moving"), fixed=view.get("frame"),
                    original_runtime_source_step=original_frame["source_step"],
                    robot_mask=original_frame.get("robot_mask_evidence", {}).get("agentview", {}).get("robot_mask_artifact"))
        rows.append(row)
    result = {"version": "microwave-dense-public-identity-inputs/1-dev", "job": source["job"],
        "source_public": {"path": str(args.public.resolve()), "sha256": hashlib.sha256(args.public.read_bytes()).hexdigest()},
        "rows": rows, "fixed_anchor": anchor, "runtime_capture_parity": parity,
        "private_labels_included": False, "train_allowed": False, "training_allowed": False, "qualification": False}
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"path": str(args.output), "frames": len(rows), "actual_controls": len(captures),
        "equal_runtime_boundaries": sum(row["RGB_pixels_equal"] and row["world_depth_equal"] for row in parity),
        "runtime_boundaries": len(parity), "private_labels_used": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
