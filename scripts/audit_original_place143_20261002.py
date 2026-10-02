"""Replay saved original-task measurements against physical predicates."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from robots.libero.v5_state import Entity, place_verified


def entity(record):
    return Entity(**{k: v for k, v in record.items() if k not in ("src", "extent")}) if record else None


def classify(measurement, *, overlap_min, contact_max):
    first, second, target = (entity(measurement[k]) for k in ("first", "second", "target"))
    relation = measurement["relation"]
    if not place_verified(first, second, target, measurement["opening"],
                          measurement["eef_xyz"], measurement["interval_s"], relation=relation):
        return False
    for current in (first, second):
        area = math.prod(max(current.upper[i] - current.lower[i], 1e-6) for i in (0, 1))
        overlap = math.prod(max(0, min(current.upper[i], target.upper[i]) -
                                   max(current.lower[i], target.lower[i])) for i in (0, 1))
        if overlap / area < overlap_min:
            return False
        if relation == "on" and abs(current.lower[2] - target.upper[2]) > contact_max:
            return False
        if relation == "in" and current.lower[2] < target.lower[2] - .01:
            return False
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expert-summary", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    summary = json.loads(a.expert_summary.read_text())
    rows, files = [], []
    for item in summary["episodes"]:
        ep = item["episode"]
        if ep["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10") or not 0 <= ep["seed"] < 5:
            raise ValueError("only registered original-task probes are allowed")
        source = Path(item["output"]) / "choices.jsonl"
        files.append({"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        for record in map(json.loads, source.read_text().splitlines()):
            evidence = record.get("predicate_verification_evidence") or {}
            truth = evidence.get("physical_placement_predicate")
            m = record.get("verification_measurements") or {}
            if truth is None or m.get("kind") != "placement":
                continue
            rows.append({"episode": ep, "decision": record["decision"],
                         "truth": bool(truth), "measurement": m,
                         "original_predicted": record["receipt"]["place_verified"]})
    reports = []
    for overlap in (.85, .90, .95):
        for contact in (.02, .015, .01):
            groups = {}
            for split, seeds in (("original_calibration", {0, 1, 2}), ("original_confirmation", {3, 4}), ("all_original", set(range(5)))):
                for relation in ("on", "in", "all"):
                    matrix = Counter()
                    for row in rows:
                        if row["episode"]["seed"] not in seeds or relation != "all" and row["measurement"]["relation"] != relation:
                            continue
                        predicted = classify(row["measurement"], overlap_min=overlap, contact_max=contact)
                        truth = row["truth"]
                        matrix["tp" if predicted and truth else "fp" if predicted else "fn" if truth else "tn"] += 1
                    tp, fp, fn = matrix["tp"], matrix["fp"], matrix["fn"]
                    groups[split + "/" + relation] = {"matrix": dict(matrix),
                        "precision": tp / (tp + fp) if tp + fp else None,
                        "recall": tp / (tp + fn) if tp + fn else None}
            reports.append({"overlap_min": overlap, "on_contact_max_m": contact, "groups": groups})
    report = {"source_summary": str(a.expert_summary),
              "source_summary_sha256": hashlib.sha256(a.expert_summary.read_bytes()).hexdigest(),
              "sources": files, "original_placement_comparisons": len(rows), "thresholds": reports,
              "scope": "original-only saved-measurement development; does not overwrite receipts or demonstrate improved closed-loop behaviour",
              "selection": "calibration seeds0-2 only; seeds3-4 independent confirmation; PRO development not read"}
    (a.output / "report.json").write_text(json.dumps(report, indent=2))
    (a.output / "measurements.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps({"comparisons": len(rows), "report_sha256": hashlib.sha256((a.output / "report.json").read_bytes()).hexdigest(),
                      "thresholds": reports}, indent=2))


if __name__ == "__main__":
    main()
