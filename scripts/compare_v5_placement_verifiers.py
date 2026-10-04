"""Recompute saved original-task measurements without rewriting any receipt."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from robots.libero.v5_verification import strict_place_verified_v2, strict_place_verified_v3, strict_place_verified_v4, strict_place_verified_v5
from scripts.rerender_v5_format118_20261002 import entity


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    """Report abstentions, precision, recall and coverage from explicit ledgers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original-training-seeds", action="store_true",
                        help="Read only original-task collection seeds 10-39 instead of original development seeds 0-4")
    args = parser.parse_args()
    counts = {name: Counter() for name in ("v2", "v3", "v4", "v5")}
    records, unavailable, sources, seen = [], [], [], set()
    for ledger in args.ledger:
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for episode in map(json.loads, ledger.read_text().splitlines()):
            identity = episode["episode"]
            assert identity["suite"] in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
            assert 10 <= identity["seed"] < 40 if args.original_training_seeds else 0 <= identity["seed"] < 5
            trace = Path(episode["output_dir"]) / "choices.jsonl"
            if str(trace) in seen:
                raise ValueError("same trace supplied twice")
            seen.add(str(trace))
            sources.append({"path": str(trace), "sha256": sha(trace)})
            for event in map(json.loads, trace.read_text().splitlines()):
                receipt = event.get("receipt") or {}
                if receipt.get("tool") not in ("place", "adjust_place"):
                    continue
                measurement = event.get("verification_measurements") or {}
                required = ("target", "opening", "eef_xyz", "interval_s", "relation")
                missing = [key for key in required if measurement.get(key) is None]
                if measurement.get("kind") != "placement" or missing:
                    unavailable.append({"episode": identity, "trace": str(trace),
                                        "decision": event["decision"], "recorded_receipt": receipt,
                                        "reason": "placement_measurements_incomplete",
                                        "missing_fields": missing,
                                        "measurement": measurement})
                    continue
                first = entity(measurement["first"]) if measurement.get("first") else None
                second = entity(measurement["second"]) if measurement.get("second") else None
                target = entity(measurement["target"])
                truth = (event.get("predicate_verification_evidence") or {}).get("physical_placement_predicate")
                values = {}
                for name, verifier in (("v2", strict_place_verified_v2), ("v3", strict_place_verified_v3),
                                       ("v4", strict_place_verified_v4), ("v5", strict_place_verified_v5)):
                    value = verifier(first, second, target, measurement["opening"], measurement["eef_xyz"],
                                     measurement["interval_s"], relation=measurement["relation"])
                    values[name] = value
                    count = counts[name]
                    count["events"] += 1
                    if truth is None:
                        count["truth_unknown"] += 1
                    else:
                        count["truth_known"] += 1
                        if value is None:
                            count["abstained_positive" if truth else "abstained_negative"] += 1
                        else:
                            count["tp" if value and truth else "fp" if value else "fn" if truth else "tn"] += 1
                records.append({"episode": identity, "trace": str(trace), "decision": event["decision"],
                                "recorded_receipt": event["receipt"], "measurement": measurement,
                                "private_recorded_truth": truth, "recomputed": values})
    metrics = {}
    for name, count in counts.items():
        predicted_positive = count["tp"] + count["fp"]
        actual_positive = count["tp"] + count["fn"] + count["abstained_positive"]
        classified = sum(count[key] for key in ("tp", "fp", "tn", "fn"))
        metrics[name] = {"counts": dict(count),
                         "precision": count["tp"] / predicted_positive if predicted_positive else None,
                         "recall_including_abstentions": count["tp"] / actual_positive if actual_positive else None,
                         "classification_coverage": classified / count["truth_known"] if count["truth_known"] else None}
    report = {"scope": "saved original measurements only; no physical rerun, no original edits or training admission",
              "source_split": "original_training_seeds_10_39" if args.original_training_seeds else "original_development_seeds_0_4",
              "unknown_policy": "unmeasured interior is unknown; abstained positives remain in recall denominator",
              "placement_attempts": len(records) + len(unavailable),
              "recomputable_events": len(records), "unrecomputable_events": len(unavailable),
              "unrecomputable_records": unavailable,
              "metric_denominator": "recomputable events; unavailable measurements are listed separately",
              "sources": sources, "metrics": metrics, "records": records, "script_sha256": sha(__file__)}
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"metrics": metrics, "output": str(args.output), "sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
