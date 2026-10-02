# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measure post-grasp RGB-D detections across a registered camera cohort."""

import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from rpent.robots.components.sam3_client import Sam3Client
from rpent.utils.rpc.http_rpc import HttpRpcClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    client = HttpRpcClient(args.endpoint)
    rows = []
    for frame in plan["frames"]:
        data = Path(frame["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == frame["sha256"]
        world_path = Path(frame["world_path"])
        assert hashlib.sha256(world_path.read_bytes()).hexdigest() == frame["world_sha256"]
        with np.load(world_path, allow_pickle=False) as saved:
            assert len(saved.files) == 1, saved.files
            world = saved[saved.files[0]]
        original = Image.open(frame["path"]).convert("RGB")
        for index, query in enumerate(plan["queries"]):
            started = time.perf_counter()
            reply = client.call("sam3.segment_all", kwargs={
                "image_base64": base64.b64encode(data).decode("ascii"),
                "text_prompt": query, "min_score": plan["min_score"],
            }, timeout_s=120)
            elapsed = time.perf_counter() - started
            detections = []
            panel = original.copy()
            draw = ImageDraw.Draw(panel)
            for instance in reply["instances"]:
                mask = Sam3Client._decode_result(instance).mask
                assert mask is not None and mask.shape == world.shape[:2]
                points = world[mask].astype(np.float64)
                points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
                if len(points) < 10:
                    continue
                lower, upper = np.quantile(points, (0.02, 0.98), axis=0)
                centre = np.median(points, axis=0)
                ys, xs = np.nonzero(mask)
                box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                draw.rectangle(box, outline="lime", width=3)
                detections.append({"score": float(instance["score"]), "pixels": int(mask.sum()),
                    "xyz": centre.tolist(), "lower": lower.tolist(), "upper": upper.tolist(),
                    "source": "perception", "eef_distance_m": float(np.linalg.norm(centre - frame["eef_xyz"])),
                    "bbox_xyxy": box})
            panel.thumbnail((384, 384))
            image_name = f'{frame["key"]}_q{index}.png'
            panel.save(args.output / image_name)
            rows.append({"frame": frame["key"], "camera": frame["camera"], "query": query,
                         "elapsed_s": elapsed, "instances": detections, "panel": image_name})
            (args.output / "rows.json").write_text(json.dumps(rows, indent=2) + "\n")
    report = {"purpose": "read-only saved RGB-D diagnosis; no physics or training labels",
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "frame_count": len(plan["frames"]), "rows": rows}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"frames": report["frame_count"], "queries": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
