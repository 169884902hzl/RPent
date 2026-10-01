"""Compare category prompts on an explicitly declared original RGB image."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    image_bytes = Path(manifest["image"]).read_bytes()
    if hashlib.sha256(image_bytes).hexdigest() != manifest["image_sha256"]:
        raise ValueError("RGB input differs from the declared image")
    args.output.mkdir(parents=True, exist_ok=False)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    facade = V5Sam3Facade(args.checkpoint)
    rows = []
    with (args.output / "prompts.jsonl").open("x") as trace:
        for prompt in manifest["prompts"]:
            started = time.perf_counter()
            reply = facade.segment_all(encoded, prompt["text"], manifest["min_score"])
            instances = []
            for index, raw in enumerate(reply["instances"]):
                mask = Sam3Client._decode_result(raw).mask
                ys, xs = np.nonzero(mask)
                hits = []
                for name, (x, y) in manifest["pixel_anchors_from_visible_rgb_only"].items():
                    if not 0 <= y < mask.shape[0] or not 0 <= x < mask.shape[1]:
                        raise ValueError("pixel anchor lies outside its declared RGB image")
                    if mask[y, x]:
                        hits.append(name)
                (args.output / f"mask_{len(rows):02d}_{index:02d}.png").write_bytes(
                    base64.b64decode(raw["mask_png_base64"])
                )
                instances.append({"score": raw["score"], "pixel_area": int(mask.sum()),
                                  "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                                  "visible_rgb_anchor_hits": hits})
            row = {**prompt, "wall_s": time.perf_counter() - started, "instances": instances}
            trace.write(json.dumps(row) + "\n")
            trace.flush()
            rows.append(row)
    summary = {"purpose": manifest["purpose"], "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
               "image_sha256": manifest["image_sha256"], "min_score": manifest["min_score"],
               "limits": manifest["limits"], "prompts": rows}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
