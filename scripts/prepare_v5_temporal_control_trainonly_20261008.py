# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Join explicitly registered r4 train-state public sequences and private labels.

No validation episode is opened. The existing runtime encoder is reused.
Missing sources remain pending; missing public evidence remains unknown.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import feature_encoder_identity, identity
from scripts.prepare_v5_temporal_endpoint_cpu import check_split, encode_sequence, read_pinned


def public_frame(saved: dict) -> dict:
    """Adapt recorded public refs without constructing camera artifact paths."""
    views, missing = {}, []
    for camera, view in saved["views"].items():
        refs = {"raw_rgb": view["files"]["rgb"], "raw_world": view["files"]["world"]}
        absent = [ref["path"] for ref in refs.values() if not Path(ref["path"]).is_file()]
        if absent:
            missing.extend(absent)
            continue
        views[camera] = {**refs, "source_step": saved["source_step"]}
    return {"source_step": saved["source_step"], "views": views,
            "public_robot_observation": saved.get("public_robot_observation"),
            "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
            "private_object_or_joint_values": False, "missing_public_files": missing}


def build_case(case: dict, profile: str):
    episode = read_pinned(case["episode"])
    measurement = read_pinned(episode["captures"]["before_off"]["public_measurements"])
    shell = measurement.get("current_stove_shell")
    chunks = read_pinned(case["public_chunks"], jsonl=True)
    bounds = {key: shell[key] for key in ("lower", "upper")} if shell and shell.get("src") == "perception" else None
    observed = measurement.get("public_observation", {}).get("robot")
    before_robot = ({"eef_xyz_m": observed["eef_xyz"], "gripper_opening_m": observed["gripper_opening"]}
                    if observed is not None else None)
    before = public_frame({"source_step": measurement["source_step"], "views": measurement["views"],
                           "public_robot_observation": before_robot})
    if ([row["chunk_index"] for row in chunks] != list(range(1, 321))
            or any(row["actual_controls"] != 5 or row["cumulative_contact_controls"] != row["chunk_index"] * 5
                   or row["source_step"] != row["public_frame"]["source_step"] for row in chunks)):
        raise ValueError("completed r4 public chunk contract is incomplete")
    steps = [before["source_step"], *[row["source_step"] for row in chunks]]
    if any(a >= b for a, b in zip(steps, steps[1:])):
        raise ValueError("public sequence source steps are stale or unordered")
    arrays, rows, recent = [], [], []
    cache = {}
    for index, record in enumerate(chunks):
        frame = public_frame(record["public_frame"])
        if frame["public_robot_observation"] != record["robot_after"]:
            raise ValueError("recorded current public proprioception differs from executed chunk")
        recent.append(frame)
        frames = recent[-3:]
        reason = ("fixture_bounds_unavailable" if bounds is None else
                  "public_proprioception_unavailable" if before_robot is None
                  or any(item["public_robot_observation"] is None for item in frames) else None)
        if reason is None:
            vector, available, reason = encode_sequence(before, frames, bounds,
                encoder_profile=profile, cache=cache)
        else:
            vector, available = np.zeros(2578, dtype=np.float32), [False, False]
        sample_id = f"{case['raw_state_sha256']}:job{case['job_id']}:off_chunk{record['chunk_index']}"
        rows.append({"sample_id": sample_id, "raw_state_sha256": case["raw_state_sha256"],
            "split": "train", "requested_mode": "turn_off", "encoder_profile": profile,
            "phase": "contact_postchunk", "chunk_index": record["chunk_index"],
            "before_frame": before, "recent_frames": frames, "measured_bounds": bounds,
            "current_available_views": available, "unknown_reason": reason,
            "src": "perception", "private_features": False,
            "public_record": {**case["public_chunks"], "line_number": index + 1},
            "public_calibration_metadata": {camera: view["files"]["metadata"]
                                            for camera, view in record["public_frame"]["views"].items()}})
        arrays.append(vector)
    # Private labels are not opened until all public vectors are complete.
    private = read_pinned(case["private_chunks"], jsonl=True)
    phases = {phase: [(line + 1, row) for line, row in enumerate(private) if row["phase"] == phase]
              for phase in ("on", "off")}
    for phase, count in (("on", 160), ("off", 320)):
        if ([row["chunk_index"] for _, row in phases[phase]] != list(range(count + 1))
                or any(row["actual_controls"] != row["chunk_index"] * 5
                       or row["controller_access"] is not False or row["affects_actions_or_stop"] is not False
                       for _, row in phases[phase])):
            raise ValueError("r4 passive private-label/action count contract changed")
    if len(private) != 482:
        raise ValueError("r4 private endpoint ledger must contain on161 + off321 rows")
    labels, pairs = [], []
    for row, record, (line, private_label) in zip(rows, chunks, phases["off"][1:]):
        if private_label["chunk_index"] != record["chunk_index"]:
            raise ValueError("private label paired to a different executed chunk")
        endpoint = private_label.get("turn_off_satisfied") if private_label.get("status") == "scored" else None
        if not isinstance(endpoint, bool) and row["unknown_reason"] is None:
            row["unknown_reason"] = "private_endpoint_label_unavailable"
        label = endpoint if isinstance(endpoint, bool) and row["unknown_reason"] is None else None
        label_ref = {**case["private_chunks"], "line_number": line}
        labels.append({"sample_id": row["sample_id"], "label": label,
                       "judge": "measured_predicate_private_joint", "controller_access": False,
                       "private_label_record": label_ref})
        pairs.append({"sample_id": row["sample_id"], "raw_state_sha256": case["raw_state_sha256"],
            "split": "train", "phase": "off", "chunk_index": record["chunk_index"],
            "source_step": record["source_step"], "cumulative_contact_controls": record["cumulative_contact_controls"],
            "public_record": row["public_record"], "private_label_record": label_ref,
            "public_truth_fields": False, "controller_reads_private_label": False})
    return arrays, rows, labels, pairs


def prepare(args):
    registry = read_pinned({"path": str(args.registry), "sha256": args.registry_sha256})
    capture = read_pinned(registry["capture_manifest"])
    if (registry["version"] != "control580-r4-train-only-registry/1" or capture["fixed_off_chunks"] != 320
            or capture["public_stop_enabled"] is not False or registry["read_validation_episodes"] is not False):
        raise ValueError("registered train-only fixed-budget contract changed")
    selection = read_pinned(capture["selection_manifest"])
    original = {case["name"]: case for case in selection["cases"]}
    registered = {case["name"]: case for case in capture["cases"]}
    if {case["name"] for case in registry["cases"]} != set(registered):
        raise ValueError("registry must name exactly the three existing r4 train states")
    source_files = registry["source_files"]
    for ref in source_files:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("registered CPU producer or runtime encoder changed")
    cases, pending = [], []
    for case in registry["cases"]:
        name = case["name"]
        if (original[name]["split"] != "train" or original[name]["raw_state_sha256"] != case["raw_state_sha256"]
                or registered[name]["state_sha256"] != case["raw_state_sha256"]
                or case["raw_state_sha256"] in selection["confirmation_raw_state_sha256"]):
            raise ValueError("source must be an explicitly registered non-confirmation train state")
        paths = {key: Path(case[key]) for key in ("boundary", "episode", "public_chunks", "private_chunks")}
        missing = [str(path) for path in paths.values() if not path.is_file()]
        if missing:
            pending.append({"name": name, "raw_state_sha256": case["raw_state_sha256"],
                            "status": "pending", "reason": "source_incomplete", "missing_paths": missing})
            continue
        boundary = read_pinned(identity(paths["boundary"]))
        if boundary.get("status") != "completed" or boundary.get("actual_contact_controls") != 2400:
            pending.append({"name": name, "status": "unknown", "reason": "physical_source_not_completed",
                            "boundary": identity(paths["boundary"])})
            continue
        episode = read_pinned(identity(paths["episode"]))
        if episode["case"]["state_sha256"] != case["raw_state_sha256"] or episode["case"]["name"] != name:
            raise ValueError("physical episode raw-state identity changed")
        cases.append({**case, "split": "train", **{key: identity(path) for key, path in paths.items()}})
    states = check_split(cases, set(selection["confirmation_raw_state_sha256"]))
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"version": "control580-r4-public-sequence-fit/1-dev", "cohort": "selection", "cases": cases,
        "pending_cases": pending, "registry": identity(args.registry), "source_files": source_files,
        "confirmation_raw_state_sha256": selection["confirmation_raw_state_sha256"],
        "confirmation_registry_complete": selection["remaining_public_state_registry_complete"],
        "encoder_profile": registry["encoder_profile"], "supports_modes": ["turn_off"],
        "feature_encoder_sha256": feature_encoder_identity(profile=registry["encoder_profile"]),
        "read_validation_episodes": False, "runtime_default_enabled": False,
        "qualification": "development only; independent validation qualification pending"}
    plan_path = args.output / "input_manifest.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    arrays, rows, labels, pairs = [], [], [], []
    for case in cases:
        x, public, private, paired = build_case(case, registry["encoder_profile"])
        arrays.extend(x); rows.extend(public); labels.extend(private); pairs.extend(paired)
    width = 2578
    features = np.stack(arrays).astype(np.float32) if arrays else np.zeros((0, width), dtype=np.float32)
    targets = np.asarray([-1 if row["label"] is None else int(row["label"]) for row in labels], dtype=np.int64)
    np.savez_compressed(args.output / "public_features.npz", features=features,
                        splits=np.asarray(["train"] * len(rows)))
    np.savez_compressed(args.output / "private_training_labels.npz", targets=targets)
    for name, records in (("public_samples.jsonl", rows), ("private_labels.jsonl", labels),
                          ("paired_samples.jsonl", pairs)):
        (args.output / name).write_text("".join(json.dumps(row) + "\n" for row in records))
    summary = {"version": "control580-r4-train-only-dataset/1", "input_manifest": identity(plan_path),
        "rows": len(rows), "feature_dimensions": width, "pending_cases": pending,
        "encoder_profile": registry["encoder_profile"], "supports_modes": ["turn_off"],
        "class_counts": {"positive": int((targets == 1).sum()), "negative": int((targets == 0).sum()),
                         "unknown": int((targets < 0).sum())},
        "raw_states": len(states["train"]), "unknown_reasons": dict(Counter(row["unknown_reason"] for row in rows if row["unknown_reason"])),
        "per_raw_state": {case["raw_state_sha256"]: {
            "positive": sum(label["label"] is True for row, label in zip(rows, labels) if row["raw_state_sha256"] == case["raw_state_sha256"]),
            "negative": sum(label["label"] is False for row, label in zip(rows, labels) if row["raw_state_sha256"] == case["raw_state_sha256"]),
            "unknown": sum(label["label"] is None for row, label in zip(rows, labels) if row["raw_state_sha256"] == case["raw_state_sha256"])} for case in cases},
        "files": [identity(args.output / name) for name in ("public_features.npz", "private_training_labels.npz",
            "public_samples.jsonl", "private_labels.jsonl", "paired_samples.jsonl")],
        "public_features_include_private_truth": False, "read_validation_episodes": False,
        "stop_admitted": False, "qualification": "development fit only; independent validation pending"}
    (args.output / "dataset_manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args)
    print(json.dumps({key: report[key] for key in ("rows", "raw_states", "class_counts", "pending_cases", "unknown_reasons")}))


if __name__ == "__main__":
    main()
