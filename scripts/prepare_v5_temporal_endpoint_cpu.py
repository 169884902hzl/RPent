# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Index and encode explicit original selection episodes for a CPU verifier.

The sampling output is addressed by its registered shard/case names. No
directory enumeration is used. Private endpoints are joined after public
features have been computed, and are stored in a separate label ledger.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import (
    CAMERAS, VERSION, feature_encoder_identity, frame_features, identity, sequence_features,
)


def read_pinned(reference: dict, *, jsonl: bool = False):
    path = Path(reference["path"])
    if identity(path)["sha256"] != reference["sha256"]:
        raise ValueError(f"input SHA changed: {path}")
    text = path.read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()] if jsonl else json.loads(text)


def check_split(cases: list[dict], excluded: set[str]) -> dict:
    """Check raw-state identity, never nominal seed alone."""
    states = {split: {case["raw_state_sha256"] for case in cases if case["split"] == split}
              for split in ("train", "validation")}
    if states["train"] & states["validation"]:
        raise ValueError("raw state appears in both train and validation")
    if (states["train"] | states["validation"]) & excluded:
        raise ValueError("confirmation raw state must not enter verifier training")
    return states


def index_frame(root: Path, source_step: int, robot: dict) -> dict:
    """Address only the four public files belonging to this recorded step."""
    views = {}
    for camera in CAMERAS:
        rgb = root / f"{camera}_high.png" / f"{source_step:02d}.png"
        world = root / f"{camera}_world_high.npz" / f"{source_step:02d}.npz"
        if rgb.is_file() and world.is_file():
            views[camera] = {"raw_rgb": identity(rgb), "raw_world": identity(world),
                             "source_step": source_step}
    return {"source_step": source_step, "views": views,
            "public_robot_observation": robot,
            "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
            "private_object_or_joint_values": False}


def encode_frame(frame: dict, bounds: dict, *, encoder_profile: str = "image_crop_v1",
                 cache: dict | None = None) -> dict:
    signatures = []
    for camera, view in frame.get("views", {}).items():
        for key in ("raw_rgb", "raw_world"):
            reference = view[key]
            stat = Path(reference["path"]).stat()
            signatures.append((camera, key, reference["path"], reference["sha256"],
                               stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    cache_key = (encoder_profile, json.dumps(bounds, sort_keys=True), tuple(signatures))
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    for view in frame.get("views", {}).values():
        for key in ("raw_rgb", "raw_world"):
            reference = view[key]
            if identity(reference["path"])["sha256"] != reference["sha256"]:
                raise ValueError("public frame SHA changed")
    features, available = frame_features(frame, bounds, profile=encoder_profile)
    result = {"features": features, "available": available}
    if cache is not None:
        cache[cache_key] = result
    return result


def encode_sequence(before: dict, recent: list[dict], bounds: dict, *,
                    encoder_profile: str = "image_crop_v1", cache: dict | None = None
                    ) -> tuple[np.ndarray, list[bool], str | None]:
    """Call the same public encoder as runtime and retain unavailable rows."""
    before_encoded = encode_frame(before, bounds, encoder_profile=encoder_profile, cache=cache)
    recent_encoded = [encode_frame(frame, bounds, encoder_profile=encoder_profile, cache=cache) for frame in recent]
    reason = None
    if len(recent) < 3:
        reason = "need_three_current_public_frames"
    observations = [frame["public_robot_observation"] for frame in recent]
    if observations:
        past = [observations[max(0, len(observations) - 3 + k)] for k in range(3)]
        proprio = {"before_eef_xyz_m": before["public_robot_observation"]["eef_xyz_m"],
                   "recent_eef_xyz_m": [item["eef_xyz_m"] for item in past],
                   "recent_gripper_opening_m": [item["gripper_opening_m"] for item in past]}
        vector = sequence_features(before_encoded, recent_encoded, proprio)
    else:
        raise ValueError("sequence requires an observed frame")
    available = recent_encoded[-1]["available"]
    if not any(available):
        reason = "fixture_unmeasured_in_both_views"
    return vector, available, reason


def build_case(case: dict, requested_mode: str, *, encoder_profile: str = "image_crop_v1"
               ) -> tuple[list[np.ndarray], list[dict], list[dict]]:
    episode = read_pinned(case["episode"])
    measurement = read_pinned(episode["captures"]["before_off"]["public_measurements"])
    shell = measurement.get("current_stove_shell")
    if shell is None or shell.get("src") != "perception":
        raise ValueError("initial fixture bounds must come from public perception")
    bounds = {key: shell[key] for key in ("lower", "upper")}
    motion = episode["off_contact"]["motion_evidence"]
    start = episode["on_setup"]["motion_evidence"][-1]
    before = {"source_step": measurement["source_step"],
              "views": {camera: {"raw_rgb": view["files"]["rgb"], "raw_world": view["files"]["world"],
                                  "source_step": measurement["source_step"]}
                        for camera, view in measurement["views"].items()},
              "public_robot_observation": {"eef_xyz_m": start["final_eef_pos"],
                                           "gripper_opening_m": start["gripper_opening"]}}
    public = read_pinned(case["public_chunks"], jsonl=True)
    labels = {row["chunk_index"]: row for row in read_pinned(case["private_chunks"], jsonl=True)
              if row["phase"] == "off"}
    if len(public) != len(motion):
        raise ValueError("public chunks and executed motion ledger length differ")
    arrays, rows, private_rows = [], [], []
    recent = []
    frame_cache = {}

    def append_sample(name, frames, phase, private_label):
        vector, available, reason = encode_sequence(before, frames, bounds,
                                                    encoder_profile=encoder_profile, cache=frame_cache)
        # Only the selected endpoint boolean is read; joints/poses stay private.
        label = private_label if isinstance(private_label, bool) and reason is None else None
        if private_label is None and reason is None:
            reason = "private_endpoint_label_unavailable"
        sample_id = f"{case['raw_state_sha256']}:job{case['job_id']}:{name}"
        rows.append({"sample_id": sample_id, "raw_state_sha256": case["raw_state_sha256"],
                     "split": case["split"], "requested_mode": requested_mode,
                     "encoder_profile": encoder_profile,
                     "phase": phase, "before_frame": before, "recent_frames": frames,
                     "measured_bounds": bounds, "current_available_views": available,
                     "unknown_reason": reason, "src": "perception",
                     "private_features": False})
        private_rows.append({"sample_id": sample_id, "label": label,
                             "judge": "measured_predicate_private_joint", "controller_access": False})
        arrays.append(vector)

    for index, record in enumerate(public):
        robot = {"eef_xyz_m": motion[index]["final_eef_pos"],
                 "gripper_opening_m": motion[index]["gripper_opening"]}
        recent.append(index_frame(Path(case["episode"]["path"]).parent, record["source_step"], robot))
        label = labels.get(record["chunk_index"], {})
        endpoint = label.get(requested_mode + "_satisfied") if label.get("status") == "scored" else None
        append_sample(f"off_chunk{record['chunk_index']}", recent[-3:], "contact_postchunk", endpoint)
    for phase, capture in case["temporal_sequences"].items():
        sequence = read_pinned(capture["public"])
        private = read_pinned(capture["private"])
        frames = sequence["frames"]
        if len(frames) != 3 or len({frame["source_step"] for frame in frames}) != 3:
            raise ValueError("registered temporal supplement needs three fresh frames")
        endpoint = (private.get("private_labels", {}).get(requested_mode, {}).get("satisfied")
                    if private.get("status") == "scored" else None)
        append_sample(phase, frames, phase, endpoint)
    return arrays, rows, private_rows


def prepare(args) -> dict:
    selection = read_pinned({"path": str(args.selection_manifest), "sha256": args.selection_manifest_sha256})
    sampling = read_pinned({"path": str(args.sampling_manifest), "sha256": args.sampling_manifest_sha256})
    if selection.get("cohort") != "selection" or sampling.get("cohort") != "selection":
        raise ValueError("verifier fitting is restricted to selection data")
    if args.requested_mode != "turn_off":
        raise ValueError("the registered 577 contact sequence contains turn_off examples only")
    selected = {case["name"]: case for case in selection["cases"]}
    cases = []
    for shard, sampled in enumerate(sampling["cases"]):
        episode_meta = sampled["episode"]
        if episode_meta["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"):
            raise ValueError("PRO data is not permitted for verifier training")
        original = selected[sampled["name"]]
        if original["raw_state_sha256"] != sampled["state_sha256"]:
            raise ValueError("selection/sampling raw-state identity mismatch")
        root = args.sampling_output / f"part{shard}" / sampled["name"]
        episode_reference = identity(root / "episode.json")
        episode = read_pinned(episode_reference)
        if episode["case"]["state_sha256"] != sampled["state_sha256"]:
            raise ValueError("recorded sampler raw-state identity mismatch")
        cases.append({"name": sampled["name"], "raw_state_sha256": sampled["state_sha256"],
                      "episode_meta": episode_meta, "split": original["split"], "job_id": args.job_id,
                      "episode": episode_reference, "public_chunks": identity(root / "public_red_chunks.jsonl"),
                      "private_chunks": identity(root / "labels_chunk.jsonl"),
                      "temporal_sequences": {phase: {"public": episode["captures"][phase]["public_temporal_sequence"],
                                                      "private": episode["captures"][phase]["private_temporal_final_label"]}
                                             for phase in sampling["phases"]}})
    excluded = set(selection["confirmation_raw_state_sha256"])
    states = check_split(cases, excluded)
    args.output.mkdir(parents=True, exist_ok=False)
    plan = {"version": "temporal-endpoint-cpu/2-dev", "cohort": "selection", "cases": cases,
            "selection_manifest": identity(args.selection_manifest), "sampling_manifest": identity(args.sampling_manifest),
            "confirmation_raw_state_sha256": sorted(excluded), "excluded_confirmation_count": len(excluded),
            "confirmation_registry_complete": selection.get("remaining_public_state_registry_complete", False),
            "supports_modes": [args.requested_mode], "encoder_profile": args.encoder_profile,
            "feature_encoder_sha256": feature_encoder_identity(profile=args.encoder_profile),
            "runtime_default_enabled": False, "all_loaders_explicit_files_only": True}
    (args.output / "input_manifest.json").write_text(json.dumps(plan, indent=2) + "\n")
    arrays, rows, labels = [], [], []
    for case in cases:
        x, public, private = build_case(case, args.requested_mode, encoder_profile=args.encoder_profile)
        arrays.extend(x); rows.extend(public); labels.extend(private)
    features = np.stack(arrays).astype(np.float32)
    targets = np.asarray([-1 if row["label"] is None else int(row["label"]) for row in labels], dtype=np.int64)
    splits = np.asarray([row["split"] for row in rows])
    np.savez_compressed(args.output / "public_features.npz", features=features, splits=splits)
    np.savez_compressed(args.output / "private_training_labels.npz", targets=targets)
    for name, records in (("public_samples.jsonl", rows), ("private_labels.jsonl", labels)):
        (args.output / name).write_text("".join(json.dumps(row) + "\n" for row in records))
    report = {"version": VERSION, "rows": len(rows), "feature_dimensions": features.shape[1],
              "input_manifest": identity(args.output / "input_manifest.json"),
              "encoder_profile": args.encoder_profile,
              "encoder_sha256": feature_encoder_identity(profile=args.encoder_profile), "supports_modes": [args.requested_mode],
              "split_counts": {split: {"registered_rows": int((splits == split).sum()),
                                       "measured_label_rows": int(((splits == split) & (targets >= 0)).sum()),
                                       "positive": int(((splits == split) & (targets == 1)).sum()),
                                       "raw_states": len(states[split])} for split in states},
              "phase_counts": dict(Counter(row["phase"] for row in rows)),
              "unknown_reasons": dict(Counter(row["unknown_reason"] for row in rows if row["unknown_reason"])),
              "confirmation_overlap": 0, "raw_state_split_overlap": 0,
              "excluded_confirmation_count": len(excluded), "public_features_include_private_truth": False,
              "scope": "five original Goal7 selection states; independent raw-state validation, no confirmation qualification",
              "files": [identity(args.output / name) for name in ("public_features.npz", "private_training_labels.npz",
                       "public_samples.jsonl", "private_labels.jsonl")],
              "stop_admitted": False}
    (args.output / "dataset_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--selection-manifest-sha256", required=True)
    parser.add_argument("--sampling-manifest", type=Path, required=True)
    parser.add_argument("--sampling-manifest-sha256", required=True)
    parser.add_argument("--sampling-output", type=Path, required=True)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--requested-mode", default="turn_off")
    parser.add_argument("--encoder-profile", choices=("image_crop_v1", "world_xy_grid_v1"), default="image_crop_v1")
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args())))


if __name__ == "__main__":
    main()
