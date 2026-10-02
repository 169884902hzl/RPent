"""Audit declared original grasp probes using private motion evidence."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from robots.libero.v5_runtime import category


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_group(ledger):
    records, categories = [], defaultdict(Counter)
    for episode in map(json.loads, ledger.read_text().splitlines()):
        identity = episode["episode"]
        path = Path(episode["output_dir"]) / "choices.jsonl"
        trace = list(map(json.loads, path.read_text().splitlines()))
        if len(trace) != 1 or not identity.get("grasp_probe_category"):
            raise ValueError("expected a registered original one-action grasp probe")
        if identity["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("motion diagnostics are original-task-only")
        event = trace[0]
        receipt = event["receipt"]
        reference = event["localization_diagnostic"]
        entities = {e["id"]: e for e in event["measurements"]}
        selected = entities[receipt["object"]]
        before, after = reference["reference"], reference["reference_after"]
        bound = [key for key, value in reference["bindings"].items()
                 if value == selected["id"] and key in before and key in after]
        binding_method = "recorded_oracle_binding"
        if not bound:
            bound = [key for key in before if key in after and category(key) == selected["name"]]
            binding_method = "unique_category_in_private_reference"
        symbol = bound[0] if len(bound) == 1 else None
        rise = after[symbol]["xyz"][2] - before[symbol]["xyz"][2] if symbol else None
        xy_offset = math.dist(selected["xyz"][:2], before[symbol]["xyz"][:2]) * 1000 if symbol else None
        opening = receipt.get("gripper_opening")
        motion = rise >= .03 and opening is not None and .005 <= opening <= .07 if rise is not None else None
        other_rises = {key: (after[key]["xyz"][2] - before[key]["xyz"][2]) * 100
                       for key in before if key in after and key != symbol
                       and category(key) == selected["name"]}
        visual = receipt.get("grasp_verified") is True
        counts = categories[identity["grasp_probe_category"]]
        counts["attempted"] += 1
        counts["visual_verified"] += visual
        counts["execution_error"] += bool(receipt.get("error"))
        counts["private_binding_unknown"] += symbol is None
        if motion is not None:
            counts["target_rise_and_aperture"] += motion
            counts["visual_negative_target_motion"] += not visual and motion
            counts["visual_positive_without_target_motion"] += visual and not motion
            counts["target_below_initial_by_3cm"] += rise <= -.03
            counts["different_same_category_raised_while_target_not_raised"] += (
                rise < .03 and any(value >= 3 for value in other_rises.values()))
        records.append({
            "episode": identity, "visual_verified": visual,
            "private_target_symbol": symbol, "private_binding_method": binding_method if symbol else None,
            "body_origin_z_rise_cm": rise * 100 if rise is not None else None,
            "measured_xy_offset_from_body_origin_mm": xy_offset,
            "target_rise_and_aperture": motion, "other_same_category_z_rises_cm": other_rises,
            "gripper_opening": opening, "stop": receipt.get("stop"), "chunks": receipt.get("chunks"),
            "error": receipt.get("error"), "wall_s": episode["result"]["wall_s"],
            "receipt": receipt, "source_trace": str(path), "source_sha256": sha(path),
        })
    counts = Counter()
    for values in categories.values():
        counts.update(values)
    xy_offsets = [r["measured_xy_offset_from_body_origin_mm"] for r in records
                  if r["measured_xy_offset_from_body_origin_mm"] is not None]
    by_category = {}
    for name, values in categories.items():
        offsets = [r["measured_xy_offset_from_body_origin_mm"] for r in records
                   if r["episode"]["grasp_probe_category"] == name
                   and r["measured_xy_offset_from_body_origin_mm"] is not None]
        by_category[name] = {**dict(values), "xy_offset_median_mm": statistics.median(offsets) if offsets else None}
    return {"ledger": str(ledger), "ledger_sha256": sha(ledger), "complete60": len(records) == 60,
            "counts": dict(counts), "by_category": {k: dict(v) for k, v in categories.items()},
            "localization_by_category": by_category,
            "xy_offset_median_mm": statistics.median(xy_offsets) if xy_offsets else None,
            "xy_offset_p95_mm": sorted(xy_offsets)[math.ceil(len(xy_offsets) * .95) - 1] if xy_offsets else None,
            "wall_median_s": statistics.median(r["wall_s"] for r in records) if records else None,
            "records": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = [read_group(ledger) for ledger in args.ledger]
    paired = None
    if len(groups) == 2:
        def key(row):
            e = row["episode"]
            return e["suite"], e["task"], e["seed"], e["grasp_probe_category"]
        left, right = ({key(r): r for r in g["records"]} for g in groups)
        common = sorted(left.keys() & right.keys())
        paired = {"n": len(common), "complete60": len(common) == 60,
                  "both_visual_verified": sum(left[k]["visual_verified"] and right[k]["visual_verified"] for k in common),
                  "left_only_visual_verified": sum(left[k]["visual_verified"] and not right[k]["visual_verified"] for k in common),
                  "right_only_visual_verified": sum(right[k]["visual_verified"] and not left[k]["visual_verified"] for k in common),
                  "both_visual_failed": sum(not left[k]["visual_verified"] and not right[k]["visual_verified"] for k in common),
                  "pairs": [{"episode": left[k]["episode"], "left": left[k], "right": right[k]} for k in common]}
    report = {"purpose": "original-only private motion diagnosis; not training labels or benchmark scores",
              "scope": "Body-origin rise and measured aperture are motion evidence, not attachment/stability. "
                       "XY displacement uses body origin as a private reference, not full-shape centre ground truth. "
                       "Different-object rise is an event, not a complete root-cause classification. "
                       "A one-action probe budget end is expected. No state or label is rewritten.",
              "groups": groups, "paired": paired, "script_sha256": sha(__file__)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"groups": [{k: v for k, v in g.items() if k != "records"} for g in groups],
                      "paired": {k: v for k, v in paired.items() if k != "pairs"} if paired else None,
                      "report_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
