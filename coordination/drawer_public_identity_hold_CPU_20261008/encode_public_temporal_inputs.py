"""Exercise the existing offline/runtime public encoder on the explicit packet."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.prepare_v5_temporal_endpoint_cpu import encode_sequence
from robots.libero.v5_temporal_verifier import feature_encoder_identity


def ref(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(item):
    if ref(item["path"])["sha256"] != item["sha256"]:
        raise ValueError("explicit temporal input changed")
    return [json.loads(line) for line in Path(item["path"]).read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(args.manifest.read_text())
    public = rows(plan["outputs"]["public_inputs.jsonl"])
    vectors, available, cache = [], [], {}
    for index, row in enumerate(public):
        if row["private_features"] or row["src"] != "perception":
            raise ValueError("public endpoint feature contract changed")
        vector, views, reason = encode_sequence(row["before_frame"], row["recent_frames"],
            row["measured_bounds"], encoder_profile="world_xy_grid_v1", cache=cache)
        if reason != row["unknown_reason"]:
            raise ValueError("offline public availability differs from indexed contract")
        if not np.isfinite(vector).all():
            raise ValueError("nonfinite public endpoint features")
        vectors.append(vector)
        available.append(views)
        if (index+1) % 50 == 0:
            print(json.dumps({"encoded_public_rows": index+1, "total": len(public)}), flush=True)
    # Join private endpoint booleans only after all public features are fixed.
    private = {row["sample_id"]: row for row in rows(plan["outputs"]["private_labels.jsonl"])}
    if len(private) != len(public):
        raise ValueError("public/private temporal sample coverage differs")
    labels = [private[row["sample_id"]]["requested_endpoint_satisfied"]
              if row["unknown_reason"] is None else -1 for row in public]
    encoded = args.output / "features.npz"
    np.savez_compressed(encoded, x=np.stack(vectors), y=np.asarray(labels, dtype=np.int8),
        available=np.asarray(available, dtype=bool),
        sample_ids=np.asarray([row["sample_id"] for row in public]),
        split=np.asarray([row["split"] for row in public]),
        requested_mode=np.asarray([row["requested_mode"] for row in public]),
        episode_group=np.asarray([row["episode_group"] for row in public]),
        feature_encoder_sha256=np.asarray(feature_encoder_identity(profile="world_xy_grid_v1")))
    report = {"manifest": ref(args.manifest), "features": ref(encoded), "rows": len(public),
        "shape": list(np.stack(vectors).shape), "all_finite": True,
        "unknown_rows_preserved": sum(value == -1 for value in labels),
        "usable_rows_by_split_mode_label": dict(Counter(
            f"{row['split']}/{row['requested_mode']}/{label}"
            for row, label in zip(public, labels) if label != -1)),
        "encoder_profile": "world_xy_grid_v1",
        "feature_encoder_sha256": feature_encoder_identity(profile="world_xy_grid_v1"),
        "model_trained": False, "runtime_admission": False, "new_physical_trials": 0}
    target = args.output / "report.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": ref(target), **report}))


if __name__ == "__main__":
    main()
