"""Summarize RPent typed-choice result.json artifacts without changing them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    for provider in ("dagger2323", "qwen4b", "jev"):
        for suite in ("libero_spatial_swap", "libero_object_swap"):
            rows = []
            base = args.root / provider / suite
            for path in sorted(base.glob("task_*_seed_*/result.json")):
                row = json.loads(path.read_text())
                rows.append(row)
            if not rows:
                continue
            success = sum(bool(row.get("official_success")) for row in rows)
            print(json.dumps({
                "provider": provider,
                "suite": suite,
                "n": len(rows),
                "success": success,
                "rate": success / len(rows),
                "episodes": [
                    {"task": row["task"], "seed": row["seed"],
                     "success": row["official_success"],
                     "decisions": row["decisions"], "video": row["video"]}
                    for row in rows
                ],
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
