"""Build a five-state development dataset with labels in a separate ledger."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import numpy as np

from public_temporal_verifier import frame_features, sequence_features, identity, VERSION


def read_pinned(reference):
    path = Path(reference["path"])
    if identity(path)["sha256"] != reference["sha256"]:
        raise ValueError(f"input SHA changed: {path}")
    return json.loads(path.read_text())


def build_case(case):
    episode = read_pinned(case["episode"])
    before_public = read_pinned(episode["captures"]["before_off"]["public_measurements"])
    shell = before_public["current_stove_shell"]
    if shell is None or shell["src"] != "perception":
        raise ValueError("initial bounds must be a measured public fixture")
    bounds = {k: shell[k] for k in ("lower", "upper")}
    initial = {"views": {camera: {"raw_rgb": x["files"]["rgb"], "raw_world": x["files"]["world"]}
                         for camera, x in before_public["views"].items()}}
    before_v, before_a = frame_features(initial, bounds)
    before = {"features": before_v, "available": before_a}
    public_path = Path(case["public_chunks"]["path"])
    private_path = Path(case["private_chunks"]["path"])
    for r in (case["public_chunks"], case["private_chunks"]):
        if identity(r["path"])["sha256"] != r["sha256"]:
            raise ValueError("chunk ledger SHA changed")
    public = [json.loads(x) for x in public_path.read_text().splitlines()]
    labels = {x["chunk_index"]: x for x in map(json.loads, private_path.read_text().splitlines()) if x["phase"] == "off"}
    motions = episode["off_contact"]["motion_evidence"]
    if len(public) != 160 or len(motions) != 160 or len(labels) != 161:
        raise ValueError("expected complete fixed-prefix public/motion/label correspondence")
    start_robot = episode["on_setup"]["motion_evidence"][-1]
    recent, features, rows, targets = [], [], [], []
    for index, obs in enumerate(public):
        current, available = frame_features(obs, bounds)
        recent.append({"features": current, "available": available})
        past = [motions[max(0, index - 2 + k)] for k in range(3)]
        proprio = {"before_eef_xyz_m": start_robot["final_eef_pos"],
            "recent_eef_xyz_m": [m["final_eef_pos"] for m in past],
            "recent_gripper_opening_m": [m["gripper_opening"] for m in past]}
        vector = sequence_features(before, recent, proprio)
        label = labels[obs["chunk_index"]]
        target = int(label["turn_off_satisfied"]) if label["status"] == "scored" and any(available) else -1
        sample_id = case["raw_state_sha256"] + f":off:{obs['chunk_index']}"
        features.append(vector); targets.append(target)
        rows.append({"sample_id": sample_id, "raw_state_sha256": case["raw_state_sha256"], "split": case["split"],
            "method": "literal_off", "requested_action": "turn_off", "source_step": obs["source_step"],
            "public_frames": {"before": initial, "recent": public[max(0, index-2):index+1]},
            "measured_bounds": bounds, "public_proprioception": proprio,
            "current_available_views": available, "unknown": target == -1,
            "context": "contact_postchunk; retreat_unobstructed_sequence_not_yet_sampled"})
    return np.stack(features), np.asarray(targets, dtype=np.int64), rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    raw_train = {c["raw_state_sha256"] for c in plan["cases"] if c["split"] == "train"}
    raw_val = {c["raw_state_sha256"] for c in plan["cases"] if c["split"] == "validation"}
    excluded = set(plan["confirmation_raw_state_sha256"])
    if raw_train & raw_val or (raw_train | raw_val) & excluded:
        raise ValueError("raw-state split or confirmation exclusion violated")
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(build_case, plan["cases"]))
    features = np.concatenate([x[0] for x in results]); targets = np.concatenate([x[1] for x in results])
    rows = [r for x in results for r in x[2]]
    splits = np.asarray([r["split"] for r in rows])
    np.savez_compressed(args.output / "public_features.npz", features=features, splits=splits)
    np.savez_compressed(args.output / "private_training_labels.npz", targets=targets)
    (args.output / "public_samples.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (args.output / "private_labels.jsonl").write_text("".join(json.dumps({"sample_id": r["sample_id"], "label": None if y == -1 else int(y), "judge": "measured_predicate_private_joint", "controller_access": False}) + "\n" for r, y in zip(rows, targets)))
    report = {"version": VERSION, "input_manifest": identity(args.manifest), "samples": len(rows), "feature_dimensions": features.shape[1],
        "raw_train_states": sorted(raw_train), "raw_validation_states": sorted(raw_val), "rawstate_overlap": 0,
        "confirmation_overlap": 0, "unknown_rows": int((targets < 0).sum()),
        "split_counts": {s: {"rows": int((splits == s).sum()), "positive": int(((splits == s) & (targets == 1)).sum())} for s in ("train", "validation")},
        "method": "literal_off", "purpose": "five-original-state CPU development baseline; not confirmation, not training admission",
        "public_features_include_private_truth": False, "unobstructed_stable_retreat_endpoint_samples": 0,
        "files": [identity(args.output / n) for n in ("public_features.npz", "private_training_labels.npz", "public_samples.jsonl", "private_labels.jsonl")]}
    (args.output / "dataset_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "files"}))


if __name__ == "__main__":
    main()
