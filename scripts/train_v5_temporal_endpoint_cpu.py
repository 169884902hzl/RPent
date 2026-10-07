# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Fit a small public temporal verifier with a pinned raw-state split on CPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import (
    feature_encoder_identity, identity, infer, model_features, model_transform_identity,
)
from scripts.prepare_v5_temporal_endpoint_cpu import check_split, read_pinned


def wilson(successes: int, trials: int) -> list[float] | None:
    if not trials:
        return None
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    radius = z * np.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [float(centre - radius), float(centre + radius)]


def metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float = .5) -> dict:
    """Report discrimination and calibration without changing endpoint labels."""
    predicted = probabilities >= threshold
    tp = int(((labels == 1) & predicted).sum())
    fp = int(((labels == 0) & predicted).sum())
    fn = int(((labels == 1) & ~predicted).sum())
    tn = int(((labels == 0) & ~predicted).sum())
    positive, negative = probabilities[labels == 1], probabilities[labels == 0]
    auc = (float(((positive[:, None] > negative[None, :]).sum()
                 + .5 * (positive[:, None] == negative[None, :]).sum())
                / (len(positive) * len(negative))) if len(positive) and len(negative) else None)
    bins = []
    for lower in np.arange(0., 1., .1):
        mask = (probabilities >= lower) & (probabilities < lower + .1 if lower < .9 else probabilities <= 1.)
        if mask.any():
            bins.append({"lower": round(float(lower), 1), "rows": int(mask.sum()),
                         "predicted_mean": float(probabilities[mask].mean()),
                         "actual_rate": float(labels[mask].mean())})
    return {"rows": len(labels), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "accuracy": float((predicted == labels).mean()) if len(labels) else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "wilson95_descriptive_frame_unit": {"accuracy": wilson(tp + tn, len(labels)),
                                                 "precision": wilson(tp, tp + fp), "recall": wilson(tp, tp + fn)},
            "auroc": auc, "brier": float(np.mean((probabilities - labels) ** 2)) if len(labels) else None,
            "fixed_classifier_threshold": threshold, "calibration_bins": bins}


def train(args) -> dict:
    import torch

    manifest = read_pinned({"path": str(args.dataset_manifest), "sha256": args.dataset_manifest_sha256})
    plan = read_pinned(manifest["input_manifest"])
    if plan.get("cohort") != "selection":
        raise ValueError("confirmation or PRO examples cannot be fitted")
    if plan.get("encoder_profile", "image_crop_v1") != args.encoder_profile:
        raise ValueError("requested encoder profile differs from prepared dataset")
    if plan["feature_encoder_sha256"] != feature_encoder_identity(profile=args.encoder_profile):
        raise ValueError("runtime/offline feature encoder identity mismatch")
    check_split(plan["cases"], set(plan["confirmation_raw_state_sha256"]))
    files = {Path(reference["path"]).name: reference for reference in manifest["files"]}
    for reference in files.values():
        if identity(reference["path"])["sha256"] != reference["sha256"]:
            raise ValueError("prepared dataset changed")
    with np.load(files["public_features.npz"]["path"], allow_pickle=False) as data:
        features, splits = data["features"], data["splits"]
    with np.load(files["private_training_labels.npz"]["path"], allow_pickle=False) as data:
        targets = data["targets"]
    rows = read_pinned(files["public_samples.jsonl"], jsonl=True)
    if len(features) != len(targets) or len(rows) != len(targets) or not np.isfinite(features).all():
        raise ValueError("dataset length or public feature validity mismatch")
    train_mask = (splits == "train") & (targets >= 0)
    validation_mask = (splits == "validation") & (targets >= 0)
    for name, mask in (("train", train_mask), ("validation", validation_mask)):
        if set(targets[mask].tolist()) != {0, 1}:
            raise ValueError(f"{name} needs both private endpoint classes")
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    inputs = model_features(features, args.feature_transform)
    mean, scale = inputs[train_mask].mean(axis=0), inputs[train_mask].std(axis=0)
    scale[scale < .02] = 1.
    x = torch.from_numpy((inputs - mean) / scale).to("cpu")
    y = torch.from_numpy(targets.astype(np.float32)).to("cpu")
    model = torch.nn.Sequential(torch.nn.Linear(features.shape[1], 32), torch.nn.ReLU(), torch.nn.Linear(32, 1)).to("cpu")
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.03)
    criterion = torch.nn.BCEWithLogitsLoss()
    best_loss, best_epoch, stale = float("inf"), 0, 0
    best_weights = None
    curve = []
    for epoch in range(1, 301):
        model.train()
        optimizer.zero_grad()
        loss = criterion(model(x[train_mask]).ravel(), y[train_mask])
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(criterion(model(x[validation_mask]).ravel(), y[validation_mask]))
        curve.append({"epoch": epoch, "train_loss": float(loss.detach()), "validation_loss": validation_loss})
        if validation_loss < best_loss - .0001:
            best_loss, best_epoch, stale = validation_loss, epoch, 0
            best_weights = {key: value.detach().clone() for key, value in model.state_dict().items()}
        else:
            stale += 1
        if stale >= 30:
            break
    model.load_state_dict(best_weights)
    model.eval()
    with torch.no_grad():
        probabilities = torch.sigmoid(model(x).ravel()).numpy()
    args.output.mkdir(parents=True, exist_ok=False)
    checkpoint = args.output / "temporal_mlp32.npz"
    np.savez_compressed(checkpoint, mean=mean, scale=scale,
                        hidden_weight=model[0].weight.detach().numpy(), hidden_bias=model[0].bias.detach().numpy(),
                        output_weight=model[2].weight.detach().numpy(), output_bias=model[2].bias.detach().numpy(),
                        supports_modes=np.asarray(plan["supports_modes"]),
                        feature_transform=np.asarray(args.feature_transform),
                        feature_transform_sha256=np.asarray(model_transform_identity()),
                        encoder_profile=np.asarray(args.encoder_profile),
                        feature_encoder_sha256=np.asarray(feature_encoder_identity(profile=args.encoder_profile)))
    predictions = [{"sample_id": row["sample_id"], "raw_state_sha256": row["raw_state_sha256"],
                    "split": row["split"], "phase": row["phase"], "requested_mode": row["requested_mode"],
                    "p_satisfied": float(p), "private_label_for_offline_analysis": None if label < 0 else int(label)}
                   for row, p, label in zip(rows, probabilities, targets)]
    (args.output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in predictions))
    (args.output / "training_curve.jsonl").write_text("".join(json.dumps(row) + "\n" for row in curve))
    # Compare every labeled offline prediction with the actual runtime function.
    errors = []
    for index in np.flatnonzero(targets >= 0):
        actual = infer(features[index], rows[index]["current_available_views"], checkpoint,
                       requested_mode=rows[index]["requested_mode"], profile=args.encoder_profile)
        if actual["status"] != "predicted" or actual["stop_admitted"]:
            raise ValueError("runtime inference contract did not preserve default no-stop")
        errors.append(abs(actual["p_satisfied"] - float(probabilities[index])))
    per_state = {}
    for state in sorted({row["raw_state_sha256"] for row in rows}):
        mask = np.asarray([row["raw_state_sha256"] == state for row in rows]) & (targets >= 0)
        per_state[state] = metrics(targets[mask], probabilities[mask])
    report = {"version": "temporal-endpoint-cpu/2-dev", "source_commit": args.source_commit,
              "model": "public dual-camera RGB-D before+three recent frames + proprioception MLP32",
              "device": "cpu", "seed": args.seed, "epochs": len(curve), "best_epoch": best_epoch,
              "early_stopped": stale >= 30, "early_stop_patience": 30,
              "dataset_manifest": identity(args.dataset_manifest), "checkpoint": identity(checkpoint),
              "supports_modes": plan["supports_modes"], "encoder_profile": args.encoder_profile,
              "feature_encoder_sha256": feature_encoder_identity(profile=args.encoder_profile),
              "feature_transform": args.feature_transform, "feature_transform_sha256": model_transform_identity(),
              "runtime_probability_max_abs_error": max(errors),
              "train": metrics(targets[train_mask], probabilities[train_mask]),
              "validation": metrics(targets[validation_mask], probabilities[validation_mask]),
              "validation_at_fixed_095": metrics(targets[validation_mask], probabilities[validation_mask], .95),
              "per_raw_state": per_state,
              "per_phase_validation": {phase: metrics(targets[mask], probabilities[mask])
                    for phase in sorted({row["phase"] for row in rows})
                    for mask in [np.asarray([row["phase"] == phase for row in rows]) & validation_mask]},
              "unknown_rows_retained": int((targets < 0).sum()),
              "stop_admitted": False, "runtime_default_enabled": False,
              "qualification": "development fit only; two raw validation states used for early stopping, no independent confirmation",
              "limitations": ["Only original Goal7 turn_off; other fixture/modes unsupported",
                              "Contact frames are correlated; frame counts are not independent trials",
                              "Wilson frame intervals are descriptive; do not infer state-level confirmation from them",
                              "Current exclusion registry incomplete; never claim comprehensive training admission"]}
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--feature-transform", choices=("raw", "baseline_relative_v1"), default="raw")
    parser.add_argument("--encoder-profile", choices=("image_crop_v1", "world_xy_grid_v1"), default="image_crop_v1")
    parser.add_argument("--seed", type=int, default=577)
    parser.add_argument("--output", type=Path, required=True)
    report = train(parser.parse_args())
    print(json.dumps({key: value for key, value in report.items() if key not in ("per_raw_state", "per_phase_validation")}))


if __name__ == "__main__":
    main()
