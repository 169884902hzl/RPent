# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Fixed-epoch CPU development fit; never open independent validation states."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import (
    feature_encoder_identity, identity, infer, model_features, model_transform_identity,
)
from scripts.prepare_v5_temporal_endpoint_cpu import check_split, read_pinned
from scripts.train_v5_temporal_endpoint_cpu import metrics


def fit(features, targets, mask, *, epochs, seed):
    if set(targets[mask].tolist()) != {0, 1}:
        return None
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(seed)
    mean, scale = features[mask].mean(axis=0), features[mask].std(axis=0)
    scale[scale < .02] = 1.
    x = torch.from_numpy((features - mean) / scale).to("cpu")
    y = torch.from_numpy(targets.astype(np.float32)).to("cpu")
    model = torch.nn.Sequential(torch.nn.Linear(features.shape[1], 32), torch.nn.ReLU(),
                                torch.nn.Linear(32, 1)).to("cpu")
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.03)
    criterion = torch.nn.BCEWithLogitsLoss()
    curve = []
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        loss = criterion(model(x[mask]).ravel(), y[mask])
        loss.backward()
        optimizer.step()
        curve.append({"epoch": epoch, "train_loss": float(loss.detach()),
                      "validation_loss": None})
    model.eval()
    with torch.no_grad():
        probabilities = torch.sigmoid(model(x).ravel()).numpy()
    return model, mean, scale, probabilities, curve


def train(args):
    manifest = read_pinned({"path": str(args.dataset_manifest), "sha256": args.dataset_manifest_sha256})
    plan = read_pinned(manifest["input_manifest"])
    profile = plan["encoder_profile"]
    if plan["cohort"] != "selection" or plan["read_validation_episodes"] is not False:
        raise ValueError("only registered selection train states may enter this fit")
    if plan["feature_encoder_sha256"] != feature_encoder_identity(profile=profile):
        raise ValueError("runtime/CPU encoder identity mismatch")
    for ref in plan["source_files"]:
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("registered CPU source changed")
    check_split(plan["cases"], set(plan["confirmation_raw_state_sha256"]))
    refs = {Path(ref["path"]).name: ref for ref in manifest["files"]}
    for ref in refs.values():
        if identity(ref["path"])["sha256"] != ref["sha256"]:
            raise ValueError("prepared public/label file SHA changed")
    with np.load(refs["public_features.npz"]["path"], allow_pickle=False) as data:
        public_features, splits = data["features"], data["splits"]
    with np.load(refs["private_training_labels.npz"]["path"], allow_pickle=False) as data:
        targets = data["targets"]
    rows = read_pinned(refs["public_samples.jsonl"], jsonl=True)
    if (len(rows) != len(targets) or len(public_features) != len(targets)
            or not np.isfinite(public_features).all() or any(split != "train" for split in splits)):
        raise ValueError("train-only dataset feature/label contract changed")
    args.output.mkdir(parents=True, exist_ok=False)
    mask = targets >= 0
    features = model_features(public_features, "baseline_relative_v1")
    fitted = fit(features, targets, mask, epochs=args.epochs, seed=args.seed)
    base = {"version": "control580-train-only-fixed-epochs/1-dev", "dataset_manifest": identity(args.dataset_manifest),
        "source_commit": args.source_commit, "encoder_profile": profile,
        "epochs": args.epochs, "seed": args.seed, "device": "cpu",
        "hyperparameters": {"hidden": 32, "optimizer": "AdamW", "lr": .001, "weight_decay": .03},
        "class_counts": {"positive": int((targets == 1).sum()), "negative": int((targets == 0).sum()),
                         "unknown": int((targets < 0).sum())},
        "read_validation_episodes": False, "validation_used_for_early_stopping": False,
        "stop_admitted": False, "runtime_default_enabled": False,
        "independent_validation_qualification": "pending", "pending_cases": plan["pending_cases"],
        "limitations": ["Training/state-group leave-one-out are selection-development results only.",
            "Three registered train raw states are not an independent confirmation batch.",
            "Correlated contact frames cannot be counted as independent state trials.",
            "No runtime stop threshold is selected or admitted by this development fit."]}
    if fitted is None:
        report = {**base, "status": "unknown", "reason": "measured_train_needs_both_endpoint_classes", "checkpoint": None}
        (args.output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    model, mean, scale, probabilities, curve = fitted
    checkpoint = args.output / "temporal_mlp32.npz"
    np.savez_compressed(checkpoint, mean=mean, scale=scale,
        hidden_weight=model[0].weight.detach().numpy(), hidden_bias=model[0].bias.detach().numpy(),
        output_weight=model[2].weight.detach().numpy(), output_bias=model[2].bias.detach().numpy(),
        supports_modes=np.asarray(["turn_off"]), feature_transform=np.asarray("baseline_relative_v1"),
        feature_transform_sha256=np.asarray(model_transform_identity()), encoder_profile=np.asarray(profile),
        feature_encoder_sha256=np.asarray(feature_encoder_identity(profile=profile)))
    predictions, errors = [], []
    for row, vector, label, p in zip(rows, public_features, targets, probabilities):
        if label >= 0:
            actual = infer(vector, row["current_available_views"], checkpoint,
                           requested_mode="turn_off", profile=profile)
            if actual["status"] != "predicted" or actual["stop_admitted"]:
                raise ValueError("runtime public-only inference/default-no-stop contract changed")
            errors.append(abs(actual["p_satisfied"] - float(p)))
        predictions.append({"sample_id": row["sample_id"], "raw_state_sha256": row["raw_state_sha256"],
            "split": "train", "phase": row["phase"], "requested_mode": "turn_off",
            "p_satisfied": float(p) if label >= 0 else None, "unknown_reason": row["unknown_reason"],
            "private_label_for_offline_analysis": int(label) if label >= 0 else None})
    states = np.asarray([row["raw_state_sha256"] for row in rows])
    folds, held_labels, held_probabilities = [], [], []
    for state in sorted(set(states.tolist())):
        train_mask, held_mask = mask & (states != state), mask & (states == state)
        result = fit(features, targets, train_mask, epochs=args.epochs, seed=args.seed)
        if result is None or not held_mask.any():
            folds.append({"held_train_raw_state": state, "status": "unknown",
                          "reason": "remaining_train_states_need_both_classes", "metrics": None})
            continue
        p = result[3][held_mask]
        folds.append({"held_train_raw_state": state, "status": "development_evaluated",
            "fit_raw_states": sorted(set(states[train_mask].tolist())), "metrics": metrics(targets[held_mask], p)})
        held_labels.extend(targets[held_mask].tolist()); held_probabilities.extend(p.tolist())
    (args.output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in predictions))
    (args.output / "training_curve.jsonl").write_text("".join(json.dumps(row) + "\n" for row in curve))
    report = {**base, "status": "development_fitted", "checkpoint": identity(checkpoint),
        "feature_encoder_sha256": feature_encoder_identity(profile=profile),
        "feature_transform": "baseline_relative_v1", "feature_transform_sha256": model_transform_identity(),
        "runtime_probability_max_abs_error": max(errors),
        "train_discrimination": metrics(targets[mask], probabilities[mask]),
        "selection_leave_one_train_state_out": {
            "folds": folds, "aggregate": metrics(np.asarray(held_labels), np.asarray(held_probabilities))
                if held_labels else None, "model_selection_or_threshold_tuning": False},
        "files": [identity(args.output / name) for name in ("predictions.jsonl", "training_curve.jsonl")]}
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--seed", type=int, default=577)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.epochs != 300 or args.seed != 577:
        parser.error("registered development fit uses fixed 300 epochs and seed577")
    report = train(args)
    print(json.dumps({key: report[key] for key in ("status", "class_counts", "independent_validation_qualification")}))


if __name__ == "__main__":
    main()
