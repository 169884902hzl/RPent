"""Explain three closed original strict6 placement mismatches without edits."""

import argparse
import dataclasses
import hashlib
import json
import math
from pathlib import Path
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    return {"path": str(path), "sha256": sha(path.read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-source", type=Path, required=True)
    parser.add_argument("--verifier-sha256", required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verifier_path = args.runtime_source / "robots/libero/v5_verification.py"
    if identity(verifier_path)["sha256"] != args.verifier_sha256:
        raise ValueError("frozen source verifier changed")
    sys.path.insert(0, str(args.runtime_source))
    from robots.libero.v5_state import Entity, place_verified
    from robots.libero.v5_verification import strict_place_verified_v6
    keys = {field.name for field in dataclasses.fields(Entity)}
    sources, selected = [], []
    for ledger in args.ledger:
        data = ledger.read_bytes()
        prefix = data[:data.rfind(b"\n") + 1]
        sources.append({"path": str(ledger), "closed_prefix_sha256": sha(prefix), "closed_prefix_bytes": len(prefix)})
        for raw_line in prefix.splitlines():
            row = json.loads(raw_line)
            first = row.get("first_attempt") or {}
            receipt, private = first.get("receipt") or {}, first.get("private_after") or {}
            if private.get("satisfied") is not True or receipt.get("place_verified") is not False or len(selected) >= 3:
                continue
            if row["case"]["episode"]["suite"] not in {"libero_spatial", "libero_object", "libero_goal", "libero_10", "libero_90"}:
                raise ValueError("original diagnostics only")
            choices = identity(Path(row["output_dir"]) / "choices.jsonl")
            if choices["sha256"] != row["choices_sha256"]:
                raise ValueError("closed choices SHA changed")
            measurements = first["verification_measurements"]
            a, b, target = [Entity(**{k: value for k, value in measurements[name].items() if k in keys})
                            for name in ("first", "second", "target")]
            opening, eef, interval = (measurements["opening"], measurements["eef_xyz"], measurements["interval_s"])
            relation = measurements["relation"]
            base = place_verified(a, b, target, opening, eef, interval, relation=relation)
            ratios, gaps = [], []
            for entity in (a, b):
                area = math.prod(max(entity.upper[i] - entity.lower[i], 1e-6) for i in (0, 1))
                overlap = math.prod(max(0., min(entity.upper[i], target.upper[i])
                                       - max(entity.lower[i], target.lower[i])) for i in (0, 1))
                ratios.append(overlap / area)
                gaps.append(abs(entity.lower[2] - target.upper[2]))
            conditions = {"two_visible_frames": bool(a.visible and b.visible),
                          "interval_at_least_300ms": interval >= .3,
                          "gripper_released_at_least_7cm": opening >= .07,
                          "two_frame_centre_stability_within_2cm": math.dist(a.xyz, b.xyz) <= .02,
                          "eef_withdrawn_at_least_5cm": math.dist(eef, b.xyz) >= .05,
                          "centres_inside_target_xy": all(target.lower[i] <= e.xyz[i] <= target.upper[i]
                                                            for e in (a, b) for i in (0, 1)),
                          "centres_above_target_top": all(e.xyz[2] > target.upper[2] for e in (a, b)),
                          "whole_bbox_footprint_overlap_at_least_90percent": all(r >= .9 for r in ratios),
                          "on_contact_gap_within_1cm": all(g <= .01 for g in gaps)}
            recomputed = strict_place_verified_v6(a, b, target, opening, eef, interval, relation=relation)
            if recomputed is not False:
                raise ValueError("historical strict6 verdict could not be reproduced")
            selected.append({"case": row["case"], "ledger": str(ledger), "ledger_row_sha256": sha(raw_line),
                             "choices": choices, "saved_public_place_verified": False,
                             "private_diagnostic_after_unchanged": private,
                             "public_before": first["public_before"], "public_after": first["public_after"],
                             "receipt": receipt, "verification_measurements": measurements,
                             "base_place_verified_recomputed": base, "strict6_recomputed": recomputed,
                             "conditions": conditions, "failed_conditions": [key for key, value in conditions.items() if not value],
                             "footprint_overlap": ratios, "footprint_minimum_unchanged": .9,
                             "on_contact_gap_m": gaps, "eef_withdrawal_distance_m": math.dist(eef, b.xyz)})
    if len(selected) != 3:
        raise ValueError("three closed mismatches have not yet been produced")
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "report.json"
    report = {"version": "original-strict6-closed-mismatch-audit/1", "verifier_source": identity(verifier_path),
              "state_source": identity(args.runtime_source / "robots/libero/v5_state.py"), "sources": sources,
              "selection": "first three private satisfied/public false mismatches in explicit ledger order; causal diagnosis, not a new evaluation score",
              "old_verdicts_changed": False, "runtime_modified": False, "new_robot_actions": 0,
              "qualification": False, "cases": selected}
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": identity(path), "cases": [{"name": case["case"]["name"],
                      "failed_conditions": case["failed_conditions"], "footprint_overlap": case["footprint_overlap"]}
                     for case in selected]}))


if __name__ == "__main__":
    main()
