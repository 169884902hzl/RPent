"""Assess public red_fraction using explicit original selection captures only."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-table", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if identity(args.capture_table)["sha256"] != args.expected_sha:
        raise ValueError("completed original capture scoring table changed")
    captures = [json.loads(line) for line in args.capture_table.read_text().splitlines()]
    if len(captures) != 100:
        raise ValueError("requires all100 fixed original selection captures")
    features, labels, references = [], [], [identity(args.capture_table)]
    for capture in captures:
        reference = capture["public_ref"]
        if identity(reference["path"])["sha256"] != reference["sha256"]:
            raise ValueError("saved public capture identity changed")
        references.append(identity(reference["path"]))
        public = json.loads(Path(reference["path"]).read_text())
        for camera, view in public["views"].items():
            packet = view.get("coil_packet") or {}
            key = capture["cell"] + ":" + capture["stage"] + ":" + camera
            features.append({"key": key, "cell": capture["cell"], "seed": capture["seed"],
                "method": capture["method"], "stage": capture["stage"], "camera": camera,
                "source_step": public["source_step"], "version": packet.get("version"),
                "state": packet.get("state"), "reason": packet.get("reason"),
                **packet.get("features", {})})
            labels.append({"key": key, "scope": "private_analysis_only_not_runtime_input",
                "true_on": capture["turn_on"], "true_off": capture["turn_off"],
                "label_class": "true_off" if capture["turn_off"] else "true_on" if capture["turn_on"] else "neither",
                "joint_qpos": capture["joint_qpos"], "private_ref": capture["private_ref"]})
    joined = [{**f, **label} for f, label in zip(features, labels)]
    distributions = []
    for camera in ("agentview", "wrist"):
        for group in ("true_off", "true_on", "neither"):
            rows = [r for r in joined if r["camera"] == camera and r["label_class"] == group]
            visible = [r for r in rows if r.get("surface_pixels", 0) >= 100 and r.get("red_fraction") is not None]
            values = [r["red_fraction"] for r in visible]
            distributions.append({"camera": camera, "label_class": group, "total": len(rows),
                "measured": len(visible), "missing": len(rows) - len(visible),
                "zero_red_fraction": sum(x == 0 for x in values),
                "minimum": min(values) if values else None, "maximum": max(values) if values else None,
                "surface_pixels_minimum": min((r["surface_pixels"] for r in visible), default=None)})
    thresholds = []
    values = sorted({r["red_fraction"] for r in joined if r.get("red_fraction") is not None})
    for threshold in sorted({0.0, .001, .005, .01, .02, .05, *values}):
        for scope in ("all_captures", "after_known_on_setup"):
            selected = [r for r in joined if r.get("surface_pixels", 0) >= 100 and r.get("red_fraction") is not None
                        and (scope == "all_captures" or r["stage"] in ("before_off", "after_contact", "post_recovery"))]
            tp = sum(r["true_off"] and r["red_fraction"] <= threshold for r in selected)
            fp = sum(not r["true_off"] and r["red_fraction"] <= threshold for r in selected)
            fn = sum(r["true_off"] and r["red_fraction"] > threshold for r in selected)
            tn = sum(not r["true_off"] and r["red_fraction"] > threshold for r in selected)
            thresholds.append({"threshold": threshold, "rule": "visible_surface>=100 AND red_fraction<=threshold",
                "scope": scope, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None})
    matching = []
    for camera in ("agentview", "wrist"):
        positives = [r for r in joined if r["camera"] == camera and r["true_off"]]
        for positive in positives:
            negatives = [r for r in joined if r["camera"] == camera and not r["true_off"]
                and r.get("surface_pixels", 0) >= 100 and r.get("red_fraction") == positive.get("red_fraction")]
            matching.append({"positive_key": positive["key"], "red_fraction": positive["red_fraction"],
                "positive_surface_pixels": positive["surface_pixels"], "negative_exact_feature_matches": len(negatives),
                "same_cell_post_recovery_counterexample": [{k: r[k] for k in ("key", "surface_pixels", "red_fraction", "label_class", "joint_qpos")}
                    for r in negatives if r["cell"] == positive["cell"] and r["stage"] == "post_recovery"]})
    report = {"version": "public-red-fraction-off-selection/1", "scope": "original Goal7 init0-4 existing selection only",
        "captures": 100, "view_rows": len(joined), "labels": dict(Counter(r["label_class"] for r in joined)),
        "distributions": distributions, "threshold_sweep": thresholds, "exact_feature_counterexamples": matching,
        "public_endpoint_stop_admitted": False, "public_endpoint_calibration_possible_from_red_fraction": False,
        "reason": "true_off and neither states have identical visible red_fraction=0 even after a publicly observed on phase; a scalar cutoff cannot distinguish the endpoint",
        "runtime_threshold": None, "private_labels_control_execution": False, "endpoint_qualified": False,
        "private_chunk_sampling_limit": "6440 private chunk scores have no synchronized public chunk captures; cannot reconstruct first-dark-chunk timing from end captures",
        "references": references, "producer": identity(Path(__file__))}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "public_features.jsonl").write_text("".join(json.dumps(r) + "\n" for r in features))
    (args.output / "private_selection_labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in labels))
    (args.output / "red_fraction_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "public_stop_calibration.json").write_text(json.dumps({"version": "stove-public-off-stop-calibration/1",
        "endpoint_stop_admitted": False, "red_fraction_threshold": None, "reason": report["reason"],
        "calibration_scope": report["scope"], "selection_report": identity(args.output / "red_fraction_report.json")}, indent=2) + "\n")
    print(json.dumps({"captures": 100, "view_rows": len(joined), "labels": report["labels"],
        "distributions": distributions, "off_stop_admitted": False,
        "zero_threshold_results": [r for r in thresholds if r["threshold"] == 0]}))


if __name__ == "__main__":
    main()
