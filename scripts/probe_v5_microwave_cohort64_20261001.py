# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare whole-fixture and door prompts on explicit saved RGB-D frames."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from rpent.robots.components.sam3_client import Sam3Client
from rpent.utils.rpc.http_rpc import HttpRpcClient

PROMPTS = ("microwave door", "open microwave door", "microwave", "microwave oven", "open microwave")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    client = HttpRpcClient(args.endpoint)
    frames, panels = [], []
    for index, frame in enumerate(manifest["frames"]):
        for path, digest in frame["file_sha256"].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
        image_bytes = Path(frame["path"]).read_bytes()
        rgb = np.asarray(Image.open(frame["path"]).convert("RGB"))
        with np.load(frame["world_path"]) as data:
            world = data["array"]
        queries = []
        for prompt_index, prompt in enumerate(PROMPTS):
            result = client.call("sam3.segment_all", kwargs={
                "image_base64": base64.b64encode(image_bytes).decode("ascii"),
                "text_prompt": prompt, "min_score": args.min_score}, timeout_s=120)
            measured, overlay = [], rgb.copy()
            for item in result["instances"]:
                mask = Sam3Client._decode_result(item).mask
                assert mask.shape == world.shape[:2]
                points = world[mask].astype(np.float64)
                points = points[np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)]
                if len(points) < 10:
                    continue
                low, high = np.quantile(points, (0.02, 0.98), axis=0)
                measured.append({"score": item["score"], "pixels": int(mask.sum()),
                                 "xyz": np.median(points, axis=0).tolist(),
                                 "lower": low.tolist(), "upper": high.tolist()})
                if item["score"] >= 0.35:
                    overlay[mask] = (overlay[mask].astype(float) * 0.5 + np.array([255, 255, 0]) * 0.5).astype(np.uint8)
            name = f"frame{index}_prompt{prompt_index}.png"
            Image.fromarray(overlay).save(args.output / name)
            panels.append({"frame": frame["key"], "prompt": prompt, "path": str(args.output / name)})
            queries.append({"prompt": prompt, "min_score": args.min_score, "measurements": measured})
        frames.append({"frame": frame["key"], "queries": queries})
        (args.output / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")
    report = {"purpose": "saved-frame class prompt diagnosis; no simulation, labels or live harness change",
              "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "frames": frames, "panels": panels, "min_score": args.min_score,
              "physics_replays": 0, "training_rows_added": 0}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"frames": len(frames), "output": str(args.output)}))


if __name__ == "__main__":
    main()
