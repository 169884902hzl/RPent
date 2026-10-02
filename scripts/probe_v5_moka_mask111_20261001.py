# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measure cross-category mask contamination in explicit saved RGB-D frames."""
import argparse
import base64
import hashlib
import json
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
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    rpc = HttpRpcClient(args.endpoint)
    rows = []
    for frame in manifest["frames"]:
        data = Path(frame["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == frame["sha256"]
        world_path = Path(frame["world_path"])
        assert hashlib.sha256(world_path.read_bytes()).hexdigest() == frame["world_sha256"]
        with np.load(world_path, allow_pickle=False) as saved:
            world = saved[saved.files[0]]
        masks = {}
        for name, query, threshold in manifest["queries"]:
            reply = rpc.call("sam3.segment_all", kwargs={"image_base64": base64.b64encode(data).decode(), "text_prompt": query, "min_score": threshold}, timeout_s=120)
            masks[name] = [(item["score"], Sam3Client._decode_result(item).mask) for item in reply["instances"]]
        pan = np.zeros(world.shape[:2], dtype=bool)
        for _, mask in masks["frypan"]:
            pan |= mask
        for index, (score, raw) in enumerate(masks["moka pot"]):
            residual = raw & ~pan
            stats = {}
            for name, mask in [("raw", raw), ("without_frypan", residual)]:
                points = world[mask].astype(np.float64)
                points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1)>1e-6)]
                stats[name] = {"pixels": int(mask.sum())}
                if len(points) >= 10:
                    lo, hi = np.quantile(points, (0.02, 0.98), axis=0)
                    stats[name].update(xyz=np.median(points,axis=0).tolist(), lower=lo.tolist(), upper=hi.tolist())
                image = Image.open(frame["path"]).convert("RGB")
                if mask.any():
                    ys,xs=np.nonzero(mask)
                    ImageDraw.Draw(image).rectangle([int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],outline="lime",width=3)
                image.thumbnail((384,384))
                image.save(args.output/f'{frame["key"]}_{index}_{name}.png')
            rows.append({"frame":frame["key"],"score":score,"frypan_instances":len(masks["frypan"]),"stats":stats})
        (args.output/"rows.json").write_text(json.dumps(rows,indent=2)+"\n")
    report={"purpose":"read-only category contamination diagnosis, no physics or training labels", "manifest_sha256":hashlib.sha256(args.manifest.read_bytes()).hexdigest(),"frames":len(manifest["frames"]),"rows":rows}
    (args.output/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"frames":report["frames"],"instances":len(rows)}))


if __name__ == "__main__":
    main()
