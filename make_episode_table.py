"""Make a compact per-episode audit table from classified result JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.root.glob("*/classified.jsonl")):
        records.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    records.sort(key=lambda row: (row.get("provider", ""), row.get("suite", ""), row.get("task", 0)))
    lines = [
        "# LIBERO-PRO Main15 Episode Audit",
        "",
        "| Provider | Suite | Task | Seed | Success | Decisions | Mean latency (s) | Failure | pi0_pick segmented before all | Video |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in records:
        video = row.get("video", "")
        lines.append(
            f"| {row.get('provider','')} | {row.get('suite','')} | {row.get('task','')} | "
            f"{row.get('seed','')} | {row.get('official_success')} | {row.get('decisions','')} | "
            f"{(row.get('mean_decision_latency_s') or 0):.3f} | {row.get('failure_category','')} | "
            f"{row.get('pi0_pick_segmented_before_all')} | [{video}]({video}) |"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} episode rows -> {args.output}")


if __name__ == "__main__":
    main()
