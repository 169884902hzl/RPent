"""Apply explicit SAM prompt/score requests to saved original RGB-D only.

This is a thin diagnostic counterpart of probe_v5_saved_segmentation.py. It
checks RGB/world SHA before use, preserves every returned raw instance, and
reports current common depth and secondary-view rejection checks. It does not
replay an environment, choose a runtime query or alter any historical verdict.
"""

import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import time

import numpy as np

from robots.libero.v5_sam3_server import V5Sam3Facade
from rpent.robots.components.sam3_client import Sam3Client


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {"path": str(path), "sha256": sha(path)}


def checked_path(descriptor):
    path = Path(descriptor["path"])
    if not descriptor.get("sha256") or sha(path) != descriptor["sha256"]:
        raise ValueError("explicit saved RGB-D identity changed: " + str(path))
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256:
        raise ValueError("registered query matrix changed")
    plan = json.loads(args.manifest.read_text())
    if plan["private_labels_in_request"] or not plan["diagnostic_only"] or plan["qualification"]:
        raise ValueError("only private-label-free saved-image diagnostics accepted")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"version": "original-saved-SAM-query-audit/1", "manifest": identity(args.manifest),
              "checkpoint": identity(args.checkpoint),
              "sam_facade_source": identity(Path(inspect.getfile(V5Sam3Facade))),
              "runtime_changed": False, "qualification": False, "new_training_rows": 0, "cases": [],
              "geometry_scope": "exact finite depth/minimum ten points plus existing secondary low-score extent gate; class/exclusion/association not invented",
              "not_replayed": ["pan-exclusion masks lack original query-to-class association in states; saved masks remain explicit diagnostic overlays",
                               "multi-query instance deduplication and semantic identity binding are not silently substituted",
                               "no private contact/hold, official predicate or simulator coordinates choose SAM masks"]}
    facade = V5Sam3Facade(str(args.checkpoint))
    for frame_index, frame in enumerate(plan["frames"]):
        rgb, world_path = checked_path(frame["image"]), checked_path(frame["world"])
        with np.load(world_path, allow_pickle=False) as data:
            world = data["array"]
        if world.ndim != 3 or world.shape[2] != 3:
            raise ValueError("saved frame world map must be HxWx3")
        encoded = base64.b64encode(rgb.read_bytes()).decode("ascii")
        results = []
        for query_index, query in enumerate(frame["queries"]):
            if query not in plan["queries"]:
                raise ValueError("frame query was not preregistered")
            started = time.perf_counter()
            result = facade.segment_all(encoded, query["text_prompt"], min_score=query["min_score"])
            instances = []
            for instance_index, item in enumerate(result.get("instances", [])):
                mask = Sam3Client._decode_result(item).mask
                if mask is None or mask.dtype.kind != "b" or mask.shape != world.shape[:2]:
                    raise ValueError("SAM mask differs from saved RGB-D dimensions")
                stem = f"frame{frame_index:02d}_query{query_index:02d}_instance{instance_index:02d}"
                mask_path = args.output / f"{stem}.png"
                mask_path.write_bytes(base64.b64decode(item["mask_png_base64"], validate=True))
                points = world[mask].astype(np.float64)
                points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
                rejection = []
                geometry = {}
                if len(points) < 10:
                    rejection.append("less_than_ten_finite_nonzero_depth_points")
                else:
                    lower, upper = np.quantile(points, (.02, .98), axis=0)
                    extent = upper - lower
                    geometry = {"lower_m": lower.tolist(), "upper_m": upper.tolist(),
                                "median_m": np.median(points, axis=0).tolist(), "extent_m": extent.tolist()}
                    if item.get("score", 0) < .5 and (np.max(extent) > .45 or np.min(extent) <= 0):
                        rejection.append("secondary_low_score_extent_over_45cm_or_degenerate")
                instances.append({"score": item.get("score"), "mask": identity(mask_path),
                                  "raw_mask_array_sha256": hashlib.sha256(mask.tobytes(order="C")).hexdigest(),
                                  "mask_pixels": int(mask.sum()), "finite_depth_points": len(points),
                                  "geometry": geometry, "common_depth_rejected": len(points) < 10,
                                  "secondary_geometry_rejection_reasons": rejection,
                                  "semantic_target_association": "unjudged; a returned mask alone is not a verified moka target"})
            results.append({"query": query, "elapsed_s": time.perf_counter() - started,
                            "raw_returned_instances": len(result.get("instances", [])), "instances": instances})
        report["cases"].append({"frame": frame, "results": results})
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    path = args.output / "report.json"
    print(json.dumps({"report": identity(path), "completed_frames": len(report["cases"]),
                      "queries": sum(len(case["results"]) for case in report["cases"]),
                      "raw_instances": sum(result["raw_returned_instances"] for case in report["cases"] for result in case["results"])}))


if __name__ == "__main__":
    main()
