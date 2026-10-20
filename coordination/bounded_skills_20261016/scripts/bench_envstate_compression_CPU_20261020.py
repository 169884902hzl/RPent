# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Compare EnvState's default and level-1 lossless RGB-D artifact encoding."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import tempfile
import time
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from rpent.session import EnvState


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for camera in ("agentview", "wrist"):
        for capture in (0, 4):
            stem = f"{capture:02d}"
            for suffix in ("png", "npz"):
                name = (
                    f"{camera}_{'high' if suffix == 'png' else 'world_high'}.{suffix}"
                )
                source = args.episode / name / f"{stem}.{suffix}"
                if suffix == "png":
                    value = iio.imread(source)
                else:
                    with np.load(source) as saved:
                        value = saved["array"]
                arms = []
                decoded = []
                for level in (None, 1):
                    with tempfile.TemporaryDirectory() as directory:
                        state = EnvState(directory, lossless_compression_level=level)
                        started = time.perf_counter()
                        if state.save(name, value, step=None) != name:
                            raise RuntimeError(f"EnvState failed to save {name}")
                        elapsed = time.perf_counter() - started
                        path = Path(directory) / name
                        round_trip = state.load(name, step=None)
                        decoded.append(round_trip)
                        arms.append(
                            {
                                "compression_level": level,
                                "wall_s": elapsed,
                                "bytes": path.stat().st_size,
                                "sha256": sha256(path),
                            }
                        )
                equal = np.array_equal(decoded[0], decoded[1], equal_nan=True)
                equal = equal and np.array_equal(decoded[0], value, equal_nan=True)
                if not equal:
                    raise RuntimeError(f"lossless round trip differs for {name}")
                rows.append(
                    {
                        "camera": camera,
                        "capture": capture,
                        "artifact": name,
                        "source_sha256": sha256(source),
                        "arms": arms,
                        "decoded_arrays_identical": True,
                    }
                )
    report = {
        "source_commit": "644398402e641b4510110b00baf08539a2cbb48a",
        "host": platform.node(),
        "training": False,
        "gpu_used": False,
        "physics_steps": 0,
        "records": rows,
        "scope": "actual EnvState.save/load on registered RGB-D arrays; same process, CPU only",
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "records": len(rows),
                "all_arrays_equal": True,
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
