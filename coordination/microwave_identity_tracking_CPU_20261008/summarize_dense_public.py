"""Summarize explicit public identity evidence, before any private pairing."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def reference(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def gaps(rows):
    result, start, end = [], None, None
    for row in rows:
        control = row["actual_control_index"]
        if not row["source_camera_distribution"]:
            if start is None:
                start = control
            end = control
        elif start is not None:
            result.append({"first_control": start, "last_control": end, "length": end - start + 1})
            start = end = None
    if start is not None:
        result.append({"first_control": start, "last_control": end, "length": end - start + 1})
    return result


def run(args):
    manifest = json.loads(args.manifest.read_text())
    audit = json.loads(args.audit.read_text())
    public = json.loads(args.public.read_text())
    if manifest["private_labels_included"] is not False or audit["private_labels_used"] is not False:
        raise ValueError("public-only diagnosis required")
    if audit["input"]["sha256"] != reference(args.manifest)["sha256"]:
        raise ValueError("audit manifest hash differs")
    if manifest["source_public"]["sha256"] != reference(args.public)["sha256"]:
        raise ValueError("source public hash differs")
    if len(audit["rows"]) != len(manifest["rows"]):
        raise ValueError("one audit row per explicit observation required")
    rows = [row for row in audit["rows"] if row["phase"] == "dense_control"]
    controls = [row["actual_control_index"] for row in rows]
    if controls != list(range(1, len(controls) + 1)):
        raise ValueError("contiguous controls required")
    inputs = {row["capture_id"]: row for row in manifest["rows"]}
    if any(row.get("stop_admitted") is not False for row in rows):
        raise ValueError("observability diagnostic cannot claim stop admission")
    cameras = ("agentview", "wrist")
    runtime = public["runtime_public_records"]
    result = {
        "version": "microwave-dense-public-identity-summary/1-dev", "job": audit["job"],
        "inputs": [reference(path) for path in (args.manifest, args.audit, args.public)],
        "actual_controls": len(rows), "baseline_frames": len(audit["rows"]) - len(rows),
        "plane_control_frames_by_camera": {
            camera: sum(row["faces"][camera] is not None for row in rows) for camera in cameras},
        "any_plane_control_frames": sum(bool(row["source_camera_distribution"]) for row in rows),
        "fresh_independent_SAM_control_frames": sum(inputs[row["capture_id"]].get("moving") is not None for row in rows),
        "additional_supported_control_frames_without_fresh_SAM": sum(
            bool(row["source_camera_distribution"]) and inputs[row["capture_id"]].get("moving") is None for row in rows),
        "missing_plane_runs": gaps(rows),
        "missing_plane_reasons_by_camera": {
            camera: dict(Counter(row["evidence"][camera].get("dual_view_reason", row["evidence"][camera].get("reason"))
                for row in rows if row["faces"][camera] is None)) for camera in cameras},
        "last_36_controls": rows[-36:],
        "runtime_candidate_count": sum(row.get("measurement", {}).get("endpoint_candidate") is True for row in runtime),
        "runtime_stop_count": sum(row.get("measurement", {}).get("stop_admitted") is True for row in runtime),
        "runtime_withdrawal_count": sum(row.get("measurement", {}).get("staged_confirmation", {}).get("withdrawal_admitted") is True
            for row in runtime),
        "private_labels_used": False, "train_allowed": False, "qualification": False,
        "unit_of_observability": "correlated_control_frames_not_independent_skill_trials",
        "stop_admitted": False, "runtime_default_changed": False,
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "last_36_controls"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
