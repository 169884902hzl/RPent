"""Index exact saved original drawer RGB-D frames; keep private labels apart."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(item):
    if ref(item["path"])["sha256"] != item["sha256"]:
        raise ValueError("registered original input changed")
    return Path(item["path"]).read_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = json.loads(args.inputs.read_text())
    features, labels, cache = [], [], {}
    groups = {"train": set(), "validation": set()}
    frame_coverage = Counter()

    def frame(root, step, robot):
        views = {}
        for camera in ("agentview", "wrist"):
            paths = {"raw_rgb": root / f"{camera}_high.png" / f"{step:02d}.png",
                     "raw_world": root / f"{camera}_world_high.npz" / f"{step:02d}.npz"}
            if all(path.is_file() for path in paths.values()):
                references = {}
                for name, path in paths.items():
                    if str(path) not in cache:
                        cache[str(path)] = ref(path)
                    references[name] = cache[str(path)]
                views[camera] = {**references, "source_step": step}
        frame_coverage[str(len(views)) + "_camera_frames"] += 1
        return {"source_step": step, "views": views, "public_robot_observation": robot,
                "coordinate_source": "calibrated_rgbd_and_robot_proprioception",
                "private_object_or_joint_values": False}

    for run in inputs["runs"]:
        for ledger in run["original_ledgers"]:
            path = Path(ledger["path"])
            for number, line in enumerate(read_pinned(ledger).splitlines(), 1):
                raw = json.loads(line)
                case, first = raw["case"], raw["first_attempt"]
                samples = first.get("verification_measurements", {}).get("drawer_public_stop", [])
                if not samples:
                    continue
                # A fixed original-seed split keeps both paired harness runs
                # of the same raw state together. No score is used to split.
                split = "validation" if case["episode"]["seed"] == 30 else "train"
                group = case["state_sha256"]
                groups[split].add(group)
                root = path.parent / case["name"] / "attempt0"
                before = samples[0]["evidence"]["before"]
                parent = next(entity for entity in first["public_before"]["entities"]
                              if entity["id"] == before["anchor_parent"])
                if parent["src"] != "perception":
                    raise ValueError("fixture crop must come from measured bounds")
                bounds = {key: parent[key] for key in ("lower", "upper")}
                start = first["public_before"]["robot"]
                before_frame = frame(root, before["source_step"], {
                    "eef_xyz_m": start["eef_xyz"], "gripper_opening_m": start["gripper_opening"]})
                motion = [entry for entry in first["motion_evidence"] if entry["name"] == "vla_act_chunk"]
                private = [entry for entry in first["contact_evidence"]["private_fixture_scores"]
                           if entry["phase"] == "after_actual_chunk"]
                recent = []
                for sample in samples:
                    chunk = sample["chunk"]
                    measured = sample["measurement"]
                    robot = motion[chunk-1]
                    recent.append(frame(root, measured["source_step"], {
                        "eef_xyz_m": robot["final_eef_pos"], "gripper_opening_m": robot["gripper_opening"]}))
                    current = recent[-3:]
                    reason = ("need_three_current_public_frames" if len(current) < 3 else
                              "public_camera_artifact_missing" if any(not f["views"] for f in [before_frame, *current])
                              else None)
                    sample_id = f"{group}:job{run['job']}:chunk{chunk}"
                    features.append({"sample_id": sample_id, "episode_group": group,
                        "split": split, "requested_mode": case["mode"], "src": "perception",
                        "before_frame": before_frame, "recent_frames": current,
                        "measured_bounds": bounds, "public_geometry": measured,
                        "encoder_profile": "world_xy_grid_v1", "unknown_reason": reason,
                        "private_features": False, "locator": {"ledger": ledger, "line_1based": number}})
                    label = private[chunk-1]["label"]["satisfied"]
                    labels.append({"sample_id": sample_id, "requested_endpoint_satisfied": label,
                                   "judge": "measured_predicate", "label_source": "private_joint_predicate",
                                   "controller_access": False})
    if groups["train"] & groups["validation"]:
        raise ValueError("same raw initial state leaked across endpoint fit and validation")
    outputs = {}
    for name, rows in (("public_inputs.jsonl", features), ("private_labels.jsonl", labels)):
        path = args.output / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        outputs[name] = ref(path)
    report = {"version": "drawer-public-temporal-inputs/1-dev", "inputs": ref(args.inputs),
        "outputs": outputs, "samples": len(features),
        "by_split_mode": dict(Counter(f["split"] + "/" + f["requested_mode"] for f in features)),
        "episode_groups_by_split": {key: sorted(values) for key, values in groups.items()},
        "split_rule": "registered seed30 validation; other registered selection seeds train; paired jobs grouped by raw-state SHA",
        "zero_raw_state_split_overlap": True, "frame_coverage": dict(frame_coverage),
        "unknown_reason_counts": dict(Counter(f["unknown_reason"] or "usable_sequence" for f in features)),
        "sampling": "saved public cadence5 contact blocks; no new physical actions",
        "new_physical_trials": 0, "qualification_authorized": False,
        "robot_decider_training_authorized": False,
        "confirmation_status": "new independent confirmation cohort still required; this packet has none",
        "encoder": "robots.libero.v5_temporal_verifier.frame_features + sequence_features (world_xy_grid_v1)",
        "future_runtime_admission": "none until independent face-identity verification passes"}
    path = args.output / "manifest.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"manifest": ref(path), "samples": len(features),
                      "unknown_reason_counts": report["unknown_reason_counts"]}))


if __name__ == "__main__":
    main()
