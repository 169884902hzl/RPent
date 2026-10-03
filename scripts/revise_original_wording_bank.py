# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Repair destination and plural wording in an explicit original-task bank."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path


def revise(text: str, original: str) -> str:
    """Keep source-location referents while making destination motion explicit."""
    if re.match(r"(?:turn|switch|activate|open|close)\b", original):
        # These instructions change a fixture state, not an object's location.
        # Also repair wording emitted by the previous destination-only pass.
        return re.sub(r"\b(turn) onto\b", r"\1 on", text, flags=re.IGNORECASE)
    if "both " in original:
        text = re.sub(r"\bit\b", "them", text)
    if original == "put the white mug on the left plate and put the yellow and white mug on the right plate":
        return text.replace(" on the left plate", " onto the left plate").replace(
            " on the right plate", " onto the right plate"
        )
    destinations = (
        (" in the basket", " into the basket"),
        (" in the bowl", " into the bowl"),
        (" on top of the cabinet", " onto the top of the cabinet"),
        (" on the rack", " onto the rack"),
        (" on the stove", " onto the stove"),
        (" on the plate", " onto the plate"),
        (" in the bottom drawer of the cabinet", " into the bottom drawer of the cabinet"),
        (" in the back compartment of the caddy", " into the back compartment of the caddy"),
    )
    # The last destination in the original identifies the intended motion goal.
    # A source such as "bowl on the stove" must remain untouched.
    matches = [(original.rfind(old), old, new) for old, new in destinations if old in original]
    if not matches:
        return text
    _, old, new = max(matches)
    before, separator, after = text.rpartition(old)
    return before + new + after if separator else text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bank = json.loads(args.input.read_text())
    revised = copy.deepcopy(bank)
    changes = []
    for task, item in revised["tasks"].items():
        original = item["instruction"]
        item["rewrites"] = [revise(text, original) for text in item["rewrites"]]
        if len(set(item["rewrites"])) != len(item["rewrites"]) or len(item["rewrites"]) < 30:
            raise ValueError(f"{task}: distinct rewrite coverage changed")
        for before, after in zip(bank["tasks"][task]["rewrites"], item["rewrites"]):
            if before != after:
                changes.append({"task": task, "before": before, "after": after})
    revised["revision"] = "original_wording252_destinations_plural_and_fixture_v2"
    revised["previous_bank_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    revised["revision_source"] = "Original-task instructions only; no PRO, human or sealed wording"
    revised["instruction_count"] = sum(len(t["rewrites"]) for t in revised["tasks"].values())
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "wording_bank.json"
    output.write_text(json.dumps(revised, indent=2, ensure_ascii=False) + "\n")
    report = {"input": str(args.input), "input_sha256": revised["previous_bank_sha256"],
              "output": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "changed_texts": len(changes), "instructions": revised["instruction_count"],
              "tasks": len(revised["tasks"]), "changes": changes,
              "fresh_binding_and_physical_label_check": "pending; wording repair is not label admission"}
    (args.output / "revision.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "changes"}, indent=2))


if __name__ == "__main__":
    main()
