# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Inspect train-state LOO public components and paired errors on CPU only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import identity, model_features
from scripts.prepare_v5_temporal_endpoint_cpu import read_pinned
from scripts.train_v5_temporal_control_trainonly_20261008 import fit
from scripts.train_v5_temporal_endpoint_cpu import metrics


def roi_profile(row):
    bounds = row["measured_bounds"]
    lower, upper = np.asarray(bounds["lower"]), np.asarray(bounds["upper"])
    extent = upper - lower
    padding = np.maximum(extent * .25, [.04, .04, .04])
    lo, hi = lower - padding, upper + padding
    eef = np.asarray(row["before_frame"]["public_robot_observation"]["eef_xyz_m"])
    distance = np.maximum(np.maximum(lo - eef, eef - hi), 0.)
    return {"measured_fixture_bounds": bounds, "public_crop_lower_m": lo.tolist(),
        "public_crop_upper_m": hi.tolist(), "before_public_eef_xyz_m": eef.tolist(),
        "before_eef_inside_padded_fixture_roi": bool((eef >= lo).all() and (eef <= hi).all()),
        "before_eef_distance_outside_roi_m": float(np.linalg.norm(distance)),
        "part_identity_measured": False,
        "limitation": "EEF location is public contact context, not evidence that a knob is localized or visible."}


def analyze(args):
    manifest = read_pinned({"path": str(args.dataset_manifest), "sha256": args.dataset_manifest_sha256})
    plan = read_pinned(manifest["input_manifest"])
    if plan["read_validation_episodes"] is not False or any(c["split"] != "train" for c in plan["cases"]):
        raise ValueError("this diagnosis must not open validation states")
    refs = {Path(ref["path"]).name: ref for ref in manifest["files"]}
    for ref in refs.values():
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("dataset source changed")
    rows = read_pinned(refs["public_samples.jsonl"], jsonl=True)
    labels = read_pinned(refs["private_labels.jsonl"], jsonl=True)
    with np.load(refs["public_features.npz"]["path"], allow_pickle=False) as data:
        raw_features = data["features"]
        features = model_features(raw_features, "baseline_relative_v1")
    with np.load(refs["private_training_labels.npz"]["path"], allow_pickle=False) as data:
        targets = data["targets"]
    states = np.asarray([row["raw_state_sha256"] for row in rows])
    valid = targets >= 0
    components = {
        "joint_public_features": features,
        "dual_rgbd_only": features[:, :2568],
        "proprioception_only": features[:, 2568:],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    records, comparisons = [], {}
    for profile, values in components.items():
        folds, all_y, all_p = [], [], []
        for state in sorted(set(states.tolist())):
            train_mask, held_mask = valid & (states != state), valid & (states == state)
            fitted = fit(values, targets, train_mask, epochs=300, seed=577)
            if fitted is None:
                folds.append({"held_train_raw_state": state, "status": "unknown"})
                continue
            p = fitted[3][held_mask]
            folds.append({"held_train_raw_state": state, "metrics": metrics(targets[held_mask], p)})
            all_y.extend(targets[held_mask].tolist()); all_p.extend(p.tolist())
            for index, probability in zip(np.flatnonzero(held_mask), p):
                row, private = rows[index], labels[index]
                predicted, actual = float(probability) >= .5, bool(targets[index])
                outcome = "tp" if predicted and actual else "fp" if predicted else "fn" if actual else "tn"
                records.append({"sample_id": row["sample_id"], "raw_state_sha256": state,
                    "component_profile": profile, "p_satisfied": float(probability),
                    "private_label_for_offline_analysis": int(actual), "outcome_at_fixed_05": outcome,
                    "public_record": row["public_record"], "private_label_record": private["private_label_record"],
                    "before_frame": row["before_frame"], "recent_frames": row["recent_frames"],
                    "current_available_views": row["current_available_views"],
                    "ROI_public_context": roi_profile(row), "stop_admitted": False})
        comparisons[profile] = {"folds": folds, "aggregate": metrics(np.asarray(all_y), np.asarray(all_p))}
    state_profiles = []
    for state in sorted(set(states.tolist())):
        selected = [row for row in rows if row["raw_state_sha256"] == state]
        mask = states == state
        current_flags = np.asarray([row["current_available_views"] for row in selected])
        proprio = np.asarray([row["recent_frames"][-1]["public_robot_observation"]["eef_xyz_m"]
                             for row in selected])
        state_profiles.append({"raw_state_sha256": state, "rows": len(selected),
            "class_counts": {"positive": int(((targets == 1) & mask).sum()),
                             "negative": int(((targets == 0) & mask).sum()),
                             "unknown": int(((targets < 0) & mask).sum())},
            "public_context": roi_profile(selected[0]),
            "available_view_rows": current_flags.sum(axis=0).tolist(),
            "before_gripper_opening_m": selected[0]["before_frame"]["public_robot_observation"]["gripper_opening_m"],
            "EEF_xyz_range_m": {"min": proprio.min(axis=0).tolist(), "max": proprio.max(axis=0).tolist()},
            "component_mean_feature_norm": {name: float(np.linalg.norm(value[mask].mean(axis=0)))
                                            for name, value in components.items()},
            "mean_current_grid_occupancy": {"agentview": float(raw_features[mask, 1920 + 4 * 64:1920 + 5 * 64].mean()),
                                            "wrist": float(raw_features[mask, 2240 + 4 * 64:2240 + 5 * 64].mean())}})
    ledger = args.output / "leave_one_train_state_predictions.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in records))
    summary = {"version": "control580-public-source-LOO-diagnosis/1-dev", "source": identity(__file__),
        "dataset_manifest": identity(args.dataset_manifest), "component_comparisons": comparisons,
        "state_public_profiles": state_profiles, "paired_predictions": identity(ledger),
        "feature_layout": "4 frames * (2 cameras * 5 channels * 8x8), 8 available flags, 10 proprio features",
        "available_flag_meaning": "at least100 measured points somewhere in padded fixture ROI, not verified control visibility",
        "source_commit": args.source_commit, "read_validation_episodes": False,
        "model_selection_or_threshold_tuning": False, "stop_admitted": False}
    path = args.output / "diagnosis.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    r = analyze(parser.parse_args())
    print(json.dumps({key: {m: val["aggregate"][m] for m in ("auroc", "precision", "recall", "brier", "fp", "fn")}
                      for key, val in r["component_comparisons"].items()}))


if __name__ == "__main__":
    main()
