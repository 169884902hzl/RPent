"""Compare category prompts on one explicit development RGB frame."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

from robots.libero.v5_sam3_server import V5Sam3Facade
from rpent.robots.components.sam3_client import Sam3Client


def main() -> None:
    """Measure category recall candidates without starting another simulator."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(args.image.read_bytes()).decode("ascii")
    facade = V5Sam3Facade(os.environ["SAM3_CHECKPOINT_PATH"])
    with args.output.open("x") as stream:
        for prompt in (
            "black bowl",
            "bowl",
            "patterned bowl",
            "ramekin",
            "ribbed ceramic bowl",
            "small ceramic ramekin",
            "white ceramic cup",
            "cup",
            "plate",
            "cookie box",
            "drawer",
            "cabinet",
            "microwave",
            "stove",
        ):
            started = time.perf_counter()
            reply = facade.segment_all(encoded, prompt, min_score=0.5)
            instances = []
            for item in reply["instances"]:
                decoded = Sam3Client._decode_result(item)
                mask = decoded.mask
                import numpy as np

                rows, cols = np.where(mask)
                instances.append(
                    {
                        "score": decoded.score,
                        "pixels": int(mask.sum()),
                        "box_xyxy": [
                            int(cols.min()),
                            int(rows.min()),
                            int(cols.max()),
                            int(rows.max()),
                        ],
                    }
                )
            record = {
                "prompt": prompt,
                "instances": instances,
                "seconds": time.perf_counter() - started,
            }
            stream.write(json.dumps(record) + "\n")
            stream.flush()
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
