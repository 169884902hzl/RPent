"""Build a deterministic index for completed LIBERO-PRO episode videos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
from pathlib import Path


TASK_RE = re.compile(r"task_(?P<task>\d+)_seed_(?P<seed>\d+)$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(root: Path):
    for video in sorted(root.glob("*/libero_*_swap/task_*_seed_*/episode.mp4")):
        episode = video.parent.name
        match = TASK_RE.fullmatch(episode)
        if match is None:
            continue
        suite = video.parent.parent.name
        provider = video.parent.parent.parent.name
        yield {
            "provider": provider,
            "suite": suite,
            "task": int(match.group("task")),
            "seed": int(match.group("seed")),
            "path": str(video),
            "bytes": video.stat().st_size,
            "sha256": digest(video),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    records = list(rows(args.root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["provider", "suite", "task", "seed", "path", "bytes", "sha256"],
        )
        writer.writeheader()
        writer.writerows(records)
    print(f"indexed {len(records)} videos -> {args.output}")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# LIBERO-PRO Main15 Videos",
            "",
            "Each link is a complete episode recording from the frozen harness.",
            "",
            "| Provider | Suite | Task | Seed | Video | SHA256 |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
        for row in records:
            link = os.path.relpath(row["path"], args.markdown_output.parent)
            lines.append(
                f"| {row['provider']} | {row['suite']} | {row['task']} | "
                f"{row['seed']} | [{row['path']}]({link}) | `{row['sha256']}` |"
            )
        args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote markdown index -> {args.markdown_output}")


if __name__ == "__main__":
    main()
