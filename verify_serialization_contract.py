"""Fail-closed comparison of one evaluation request and one training row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from robots.libero.serialization import assert_training_eval_compatible


def _read(path: Path) -> dict:
    text = path.read_text()
    # Training data is commonly JSONL; use the first non-empty row for the
    # preflight comparison and report the exact source path to the caller.
    for line in text.splitlines():
        if line.strip():
            return json.loads(line)
    raise ValueError(f"empty request file: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    args = parser.parse_args()
    assert_training_eval_compatible(_read(args.evaluation), _read(args.training))
    print("serialization_contract=ok")


if __name__ == "__main__":
    main()
