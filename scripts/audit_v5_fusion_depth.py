"""Replay a recorded original-task RGB-D fusion without changing its labels."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_perception_geometry import fuse_cloud, measured_points


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--decision", required=True, type=int)
    parser.add_argument("--entity", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.trace.parent
    config = json.loads((root / "config.json").read_text())
    if config["libero_type"] != "standard":
        raise ValueError("fusion diagnosis requires an original task")
    event = next(json.loads(line) for line in args.trace.read_text().splitlines()
                 if json.loads(line)["decision"] == args.decision)
    evidence = event["perception_measurement_evidence"][args.entity]
    if not evidence["fusion"]["fused"]:
        raise ValueError("the registered measurement did not fuse both views")
    clouds, sources = [], []
    for view in evidence["source_cameras"]:
        record = evidence["sam_mask_files"][view]
        mask_path = Path(record["path"])
        if sha(mask_path) != record["sha256"]:
            raise ValueError("registered SAM mask changed")
        world_path = root / f"{view}_world_high.npz" / f"{record['source_step']:02d}.npz"
        with np.load(mask_path) as stored:
            mask = stored["array"].astype(bool)
        with np.load(world_path) as stored:
            world = stored["array"]
        clouds.append(measured_points(world, mask))
        sources.append({"view": view, "mask": str(mask_path), "mask_sha256": sha(mask_path),
                        "depth": str(world_path), "depth_sha256": sha(world_path)})
    if len(clouds) != 2:
        raise ValueError("expected the two registered measurement views")
    outcomes = {}
    for arm, enabled in (("before", False), ("after", True)):
        cloud, index, detail = fuse_cloud(clouds[0], [(clouds[1], evidence["fusion"]["secondary_score"])],
                                          trim_depth_tails=enabled)
        if index != 0:
            raise ValueError("recorded measurement no longer uniquely associates")
        lower, upper = np.quantile(cloud, (.02, .98), axis=0)
        outcomes[arm] = {"lower": lower.tolist(), "upper": upper.tolist(),
                         "extent_cm": ((upper - lower) * 100).tolist(),
                         "footprint_centre": ((upper[:2] + lower[:2]) / 2).tolist(),
                         "median": np.median(cloud, axis=0).tolist(), "fusion": detail}
    recorded = next(e for e in event["measurements"] if e["id"] == args.entity)
    reproduction_error = float(np.max(np.abs(np.array([
        outcomes["before"]["lower"], outcomes["before"]["upper"]])
        - np.array([recorded["lower"], recorded["upper"]]))))
    report = {"scope": "original saved RGB-D CPU fusion only; no physical replay or model score",
              "trace": str(args.trace), "trace_sha256": sha(args.trace),
              "decision": args.decision, "entity": args.entity, "sources": sources,
              "recorded_entity": recorded, "reproduction_max_bounds_error_m": reproduction_error,
              "outcomes": outcomes, "label_changes": 0, "new_training_rows": 0,
              "fusion_module_sha256": sha(Path(__file__).resolve().parents[1]
                                           / "robots/libero/v5_perception_geometry.py")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"reproduction_max_bounds_error_m": reproduction_error,
                      "before_extent_cm": outcomes["before"]["extent_cm"],
                      "after_extent_cm": outcomes["after"]["extent_cm"],
                      "report": str(args.output), "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
