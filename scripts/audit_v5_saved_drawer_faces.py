"""Recompute original drawer endpoints from explicit recorded depth captures."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_fixture_parts import measured_drawer_faces
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import measured_fixture_endpoint


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    counts, records, sources = Counter(), [], {}
    for episode in map(json.loads, args.ledger.read_text().splitlines()):
        identity = episode["episode"]
        if identity["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("endpoint calibration is original-task-only")
        trace = Path(episode["output_dir"]) / "choices.jsonl"
        sources[str(trace)] = sha(trace)
        anchors = {}
        for event in map(json.loads, trace.read_text().splitlines()):
            receipt = event["receipt"]
            if receipt["tool"] != "articulate":
                continue
            entities = {e["id"]: Entity(**{k: v for k, v in e.items() if k in Entity.__dataclass_fields__})
                        for e in event["measurements"]}
            part = entities[receipt["object"]]
            parent = entities.get(part.part_of)
            if not parent or parent.name != "cabinet" or "drawer" not in part.name:
                continue
            counts["attempts"] += 1
            axis = event["fixture_measurement_evidence"].get(parent.id, {}).get("fixture_front_axis")
            anchors.setdefault(part.id, (parent, part, axis))
            evidence = (event.get("verification_measurements") or {}).get("articulation") or {}
            samples = []
            for key in ("before", "after"):
                step = (evidence.get(key) or {}).get("source_step")
                path = Path(episode["output_dir"]) / "agentview_world_high.npz" / f"{step:02d}.npz" if step is not None else None
                if path is None or not path.exists():
                    samples.append(None)
                    continue
                sources[str(path)] = sha(path)
                with np.load(path) as data:
                    world = data[data.files[0]]
                measured, _ = measured_drawer_faces(world, *anchors[part.id])
                samples.append({**measured, "source_step": step, "world_path": str(path), "world_sha256": sources[str(path)]})
            result, geometry = measured_fixture_endpoint(*samples, receipt["mode"], drawer=True)
            truth = (event.get("predicate_verification_evidence") or {}).get("physical_articulation_predicate")
            counts["measurement_unknown"] += result is None
            counts["truth_unknown"] += truth is None
            if result is not None and truth is not None:
                counts["tp" if result and truth else "fp" if result else "fn" if truth else "tn"] += 1
            if result is None and truth is not None:
                counts["positive_abstention" if truth else "negative_abstention"] += 1
            records.append({"episode": identity, "decision": event["decision"], "selected": event["selected"],
                            "old_verified": receipt.get("articulate_verified"), "measured_verified": result,
                            "physical_predicate": truth, "evidence": geometry})
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    report = {
        "scope": "saved original RGB-D calibration; no result, training row or receipt is overwritten; not runtime validation",
        "ledger": str(args.ledger), "ledger_sha256": sha(args.ledger), "script_sha256": sha(__file__),
        "counts": dict(counts), "precision": tp / (tp + fp) if tp + fp else None,
        "recall_on_measured_subset": tp / (tp + fn) if tp + fn else None,
        "recall_including_positive_abstention": tp / (tp + fn + counts["positive_abstention"]) if tp + fn + counts["positive_abstention"] else None,
        "sources": sources, "records": records,
    }
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("sources", "records")}))
    print("REPORT_SHA256", sha(args.output))


if __name__ == "__main__":
    main()
