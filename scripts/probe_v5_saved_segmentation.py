"""Compare SAM prompts on explicitly registered RGB-D captures, without replay."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from robots.libero.v5_sam3_server import V5Sam3Facade
from rpent.robots.components.sam3_client import Sam3Client


def measured_seed(world, lower, upper):
    """Find an interior current-depth pixel within the prior measured object."""
    from scipy.ndimage import distance_transform_edt

    lower, upper = np.asarray(lower), np.asarray(upper)
    valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
    support = valid & np.all(world >= lower - .01, axis=2) & np.all(world <= upper + .01, axis=2)
    support &= world[..., 2] >= lower[2] + .35 * (upper[2] - lower[2])
    if np.count_nonzero(support) < 10:
        return None
    distance = distance_transform_edt(support)
    return list(map(int, np.unravel_index(np.argmax(distance), support.shape)))


def main() -> None:
    """Keep raw masks, scores and measured bounds for every attempted prompt."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    facade = V5Sam3Facade(args.checkpoint)
    report = {"purpose": "saved RGB-D segmentation diagnosis; not training or model evaluation",
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(), "cases": []}
    for case in json.loads(args.manifest.read_text())["cases"]:
        rgb = Path(case["rgb"])
        depth = Path(case["world"])
        with np.load(depth) as data:
            world = data[data.files[0]].astype(float)
        encoded = base64.b64encode(rgb.read_bytes()).decode("ascii")
        results = []
        seed = measured_seed(world, case["lower"], case["upper"]) if "lower" in case else None
        prompts = [("text", text) for text in case["prompts"]]
        if seed is not None:
            prompts.append(("point", seed))
        if "lower" in case:
            from robots.libero.v5_perception_geometry import measured_prompt_pixel
            surface_seed = measured_prompt_pixel(world, case["lower"], case["upper"])
            if surface_seed is not None and surface_seed != seed:
                prompts.append(("point", surface_seed))
        for index, (kind, prompt) in enumerate(prompts):
            started = time.perf_counter()
            if kind == "point":
                result = facade.segment(encoded, point=prompt, min_score=.2)
                instances = [result] if result.get("found") else []
            else:
                result = facade.segment_all(encoded, prompt, min_score=.25)
                instances = result.get("instances", [])
            measured = []
            for j, item in enumerate(instances):
                mask = Sam3Client._decode_result(item).mask
                points = world[mask]
                points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
                if len(points) < 10:
                    measured.append({"score": item.get("score"), "valid_depth_pixels": len(points)})
                    continue
                lo, hi = np.quantile(points, (.02, .98), axis=0)
                filename = f"{case['name']}_{index}_{j}.png"
                (args.output / filename).write_bytes(base64.b64decode(item["mask_png_base64"]))
                measured.append({"score": item.get("score"), "mask": filename,
                                 "valid_depth_pixels": len(points), "lower": lo.tolist(),
                                 "upper": hi.tolist(), "median": np.median(points, axis=0).tolist()})
            results.append({"kind": kind, "prompt": prompt, "elapsed_s": time.perf_counter() - started,
                            "instances": measured, "found": bool(instances), "reason": result.get("reason")})
        report["cases"].append({"case": case, "seed": seed, "rgb_sha256": hashlib.sha256(rgb.read_bytes()).hexdigest(),
                                "world_sha256": hashlib.sha256(depth.read_bytes()).hexdigest(), "results": results})
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
