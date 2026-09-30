# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Audit adapter vocabulary on explicit saved original-task camera frames."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from robots.libero.v5_sam3_server import V5Sam3Facade
from rpent.robots.components.sam3_client import Sam3Client


def main() -> None:
    """Preserve production-threshold masks for every named diagnostic prompt."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    probes = json.loads(args.manifest.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    facade = V5Sam3Facade(os.environ["SAM3_CHECKPOINT_PATH"])
    with args.output.open("x") as stream:
        for probe in probes:
            image = Path(probe["image"]).read_bytes()
            encoded = base64.b64encode(image).decode("ascii")
            for prompt in probe["prompts"]:
                start = time.perf_counter()
                reply = facade.segment_all(encoded, prompt, min_score=0.5)
                instances = []
                for item in reply["instances"]:
                    result = Sam3Client._decode_result(item)
                    rows, cols = np.where(result.mask)
                    instances.append(
                        {
                            "score": result.score,
                            "pixels": int(result.mask.sum()),
                            "box_xyxy": [
                                int(cols.min()),
                                int(rows.min()),
                                int(cols.max()),
                                int(rows.max()),
                            ],
                        }
                    )
                record = {
                    "scene": probe["scene"],
                    "image": probe["image"],
                    "image_sha256": hashlib.sha256(image).hexdigest(),
                    "prompt": prompt,
                    "instances": instances,
                    "seconds": time.perf_counter() - start,
                }
                stream.write(json.dumps(record) + "\n")
                stream.flush()
                print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
