# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Report train-only threshold selection and state-level endpoint replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import identity
from scripts.prepare_v5_temporal_endpoint_cpu import read_pinned
from scripts.train_v5_temporal_endpoint_cpu import metrics


def summarize(args) -> dict:
    dataset = read_pinned({"path": str(args.dataset_manifest), "sha256": args.dataset_manifest_sha256})
    plan = read_pinned(dataset["input_manifest"])
    report = read_pinned({"path": str(args.training_report), "sha256": args.training_report_sha256})
    if report["dataset_manifest"]["sha256"] != args.dataset_manifest_sha256 or plan["cohort"] != "selection":
        raise ValueError("summary is restricted to the registered selection fit")
    predictions = [json.loads(line) for line in args.predictions.read_text().splitlines() if line.strip()]
    public_reference = next(ref for ref in dataset["files"] if Path(ref["path"]).name == "public_samples.jsonl")
    public = {row["sample_id"]: row for row in read_pinned(public_reference, jsonl=True)}
    if len(predictions) != dataset["rows"] or {row["sample_id"] for row in predictions} != set(public):
        raise ValueError("prediction/public-ledger identity mismatch")
    selected = {split: [row for row in predictions if row["split"] == split
                        and row["private_label_for_offline_analysis"] is not None]
                for split in ("train", "validation")}

    def score(rows, threshold):
        return metrics(np.asarray([row["private_label_for_offline_analysis"] for row in rows]),
                       np.asarray([row["p_satisfied"] for row in rows]), threshold)

    choices = []
    for threshold in sorted({.5, .95, *(row["p_satisfied"] for row in selected["train"]
                                       if row["p_satisfied"] >= .5)}):
        result = score(selected["train"], threshold)
        if result["precision"] is not None and result["precision"] >= .95:
            choices.append((result["recall"], result["precision"], threshold))
    if not choices:
        raise ValueError("no train-only threshold reaches the development precision target")
    threshold = max(choices)[2]
    failures = []
    for row in predictions:
        label = row["private_label_for_offline_analysis"]
        if label is not None and (row["p_satisfied"] >= threshold) != bool(label):
            observation = public[row["sample_id"]]
            failures.append({**row, "failure": "false_stop" if label == 0 else "missed_endpoint",
                             "private_label_use": "offline_analysis_only",
                             "before_frame": observation["before_frame"],
                             "recent_frames": observation["recent_frames"],
                             "current_available_views": observation["current_available_views"]})
    per_state = []
    for case in plan["cases"]:
        contact = [row for row in selected[case["split"]]
                   if row["raw_state_sha256"] == case["raw_state_sha256"]
                   and row["phase"] == "contact_postchunk"]
        first = next((row for row in contact if row["p_satisfied"] >= threshold), None)
        per_state.append({"name": case["name"], "raw_state_sha256": case["raw_state_sha256"],
                          "split": case["split"], "contact_rows": len(contact),
                          "any_true_endpoint": any(row["private_label_for_offline_analysis"] for row in contact),
                          "first_threshold_crossing": first,
                          "max_probability": max(row["p_satisfied"] for row in contact),
                          "offline_threshold_metrics": score(contact, threshold)})
    validation_states = [row for row in per_state if row["split"] == "validation"]
    result = {"version": "temporal-endpoint-train-threshold/1-dev",
              "source": identity(__file__), "dataset_manifest": identity(args.dataset_manifest),
              "training_report": identity(args.training_report), "predictions": identity(args.predictions),
              "threshold_selected_on": "train rows only",
              "selection_rule": "threshold >= .5; train precision >= .95; maximize recall, then precision, then threshold",
              "selected_threshold": threshold,
              "train": score(selected["train"], threshold),
              "validation": score(selected["validation"], threshold), "per_raw_state": per_state,
              "validation_raw_state_replay": {
                  "states": len(validation_states),
                  "correct_first_stop": sum(row["first_threshold_crossing"] is not None
                      and row["first_threshold_crossing"]["private_label_for_offline_analysis"] == 1 for row in validation_states),
                  "false_first_stop": sum(row["first_threshold_crossing"] is not None
                      and row["first_threshold_crossing"]["private_label_for_offline_analysis"] == 0 for row in validation_states),
                  "missed_true_endpoint": sum(row["any_true_endpoint"]
                      and row["first_threshold_crossing"] is None for row in validation_states)},
              "failure_rows": len(failures), "stop_admitted": False, "runtime_default_enabled": False,
              "limitations": report["limitations"] + [
                  "Frame discrimination does not qualify raw-state physical stop performance",
                  "Replay uses recorded contact sequences and does not replace a new physical rollout",
                  "Threshold was fitted on train; validation raw states were already used for model early stopping"]}
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = args.output / "failure_evidence.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in failures))
    result["failure_evidence"] = identity(ledger)
    (args.output / "threshold_analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--training-report", type=Path, required=True)
    parser.add_argument("--training-report-sha256", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    report = summarize(parser.parse_args())
    print(json.dumps({"selected_threshold": report["selected_threshold"],
                      "validation_raw_state_replay": report["validation_raw_state_replay"],
                      "failure_evidence": report["failure_evidence"]}))


if __name__ == "__main__":
    main()
