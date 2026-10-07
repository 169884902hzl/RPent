"""Prepare, fit train-only, then evaluate the registered drawer val once."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_temporal_verifier import (
    feature_encoder_identity, infer, model_features, model_transform_identity,
)
from scripts.train_v5_temporal_control_trainonly_20261008 import fit
from scripts.train_v5_temporal_endpoint_cpu import metrics


PROFILE = "world_xy_grid_v1"
TRANSFORM = "baseline_relative_v1"
RECIPE = {"epochs": 300, "seed": 577, "hidden": 32, "optimizer": "AdamW",
          "lr": .001, "weight_decay": .03, "feature_transform": TRANSFORM,
          "scaling": "train-only mean/std; std<.02 becomes1", "thresholds": [.5, .95],
          "early_stopping": False, "threshold_selection": False,
          "model_selection": "final epoch300 only", "modes": ["open", "close"]}


def identity(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def pinned(item):
    path = Path(item["path"])
    if identity(path)["sha256"] != item["sha256"]:
        raise ValueError("registered explicit input changed: " + str(path))
    return path


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare(args):
    encoded = json.loads(args.encoded_report.read_text())
    inputs = json.loads(pinned(encoded["manifest"]).read_text())
    public = [json.loads(line) for line in pinned(inputs["outputs"]["public_inputs.jsonl"]).read_text().splitlines()]
    with np.load(pinned(encoded["features"]), allow_pickle=False) as data:
        x, y, split, modes, groups, ids, available = [np.array(data[key], copy=True)
            for key in ("x", "y", "split", "requested_mode", "episode_group", "sample_ids", "available")]
        encoder = str(data["feature_encoder_sha256"].item())
    if encoder != feature_encoder_identity(profile=PROFILE) or len(public) != len(x):
        raise ValueError("shared public feature contract changed")
    if [row["sample_id"] for row in public] != ids.tolist():
        raise ValueError("public row order differs from encoded features")
    if set(groups[split == "train"]) & set(groups[split == "validation"]):
        raise ValueError("paired raw state overlaps fixed train/val split")
    args.output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name in ("train", "validation"):
        mask = split == name
        path = args.output / (name + ".npz")
        np.savez_compressed(path, x=x[mask], y=y[mask], mode=modes[mask],
            groups=groups[mask], sample_ids=ids[mask],
            available=available[mask])
        files[name] = identity(path)
    refs = [identity(__file__)]
    import inspect
    refs.extend(identity(inspect.getfile(function)) for function in (fit, metrics, model_features))
    plan = {"version": "drawer-public-fixed-train14-val6/1-dev",
        "source_commit": args.source_commit, "source_files": refs,
        "encoded_report": identity(args.encoded_report), "public_manifest": encoded["manifest"],
        "files": files, "recipe": RECIPE, "feature_encoder_sha256": encoder,
        "feature_transform_sha256": model_transform_identity(),
        "counts": {name: {"rows": int((split == name).sum()),
                         "raw_states": len(set(groups[split == name])),
                         "by_mode_label": dict(Counter(f"{mode}/{label}" for mode, label
                             in zip(modes[split == name], y[split == name])))}
                   for name in ("train", "validation")},
        "private_labels_used_as_features": False, "preparation_opened_existing_encoded_val": True,
        "training_may_open": ["train"], "evaluation_may_open": ["validation"],
        "evaluation_protocol": "after both final-epoch checkpoints fixed, evaluate validation once at preregistered thresholds .5 and .95",
        "confirmation_authorized": False, "runtime_admission": False,
        "decider_training_authorized": False, "new_physical_trials": 0}
    dump(args.output / "fit_manifest.json", plan)
    return {"manifest": identity(args.output / "fit_manifest.json"), "counts": plan["counts"]}


def read_plan(args):
    if identity(args.manifest)["sha256"] != args.manifest_sha:
        raise ValueError("preregistered fit recipe changed")
    plan = json.loads(args.manifest.read_text())
    if plan["recipe"] != RECIPE:
        raise ValueError("fixed hyperparameters changed")
    for ref in plan["source_files"]:
        pinned(ref)
    if plan["feature_encoder_sha256"] != feature_encoder_identity(profile=PROFILE):
        raise ValueError("public encoder changed")
    return plan


def fit_train(args):
    plan = read_plan(args)
    # The only dataset read by this stage is the separately pinned train file.
    with np.load(pinned(plan["files"]["train"]), allow_pickle=False) as data:
        raw, labels, modes, ids, groups, available = [np.array(data[key], copy=True)
            for key in ("x", "y", "mode", "sample_ids", "groups", "available")]
    args.output.mkdir(parents=True, exist_ok=False)
    transformed = model_features(raw, TRANSFORM)
    outputs, report_modes, prediction_rows = {}, {}, []
    for mode in RECIPE["modes"]:
        chosen = modes == mode
        x, y = transformed[chosen], labels[chosen]
        trained = fit(x, y, y >= 0, epochs=300, seed=577)
        if trained is None:
            raise ValueError("registered train mode lacks both endpoint classes")
        model, mean, scale, probabilities, curve = trained
        path = args.output / ("drawer_" + mode + "_mlp32.npz")
        np.savez_compressed(path, mean=mean, scale=scale,
            hidden_weight=model[0].weight.detach().numpy(), hidden_bias=model[0].bias.detach().numpy(),
            output_weight=model[2].weight.detach().numpy(), output_bias=model[2].bias.detach().numpy(),
            supports_modes=np.asarray([mode]), feature_transform=np.asarray(TRANSFORM),
            feature_transform_sha256=np.asarray(model_transform_identity()),
            encoder_profile=np.asarray(PROFILE),
            feature_encoder_sha256=np.asarray(feature_encoder_identity(profile=PROFILE)))
        outputs[mode] = identity(path)
        errors = []
        for row_index, p in zip(np.flatnonzero(chosen), probabilities):
            actual = infer(raw[row_index], available[row_index].tolist(), path, requested_mode=mode, profile=PROFILE)
            if actual["status"] != "predicted" or actual["stop_admitted"]:
                raise ValueError("public-only runtime default-no-stop inference changed")
            errors.append(abs(actual["p_satisfied"] - float(p)))
            prediction_rows.append({"sample_id": str(ids[row_index]), "raw_state_sha256": str(groups[row_index]),
                "split": "train", "mode": mode, "p_satisfied": float(p),
                "private_label_for_offline_analysis": int(labels[row_index]) if labels[row_index] >= 0 else None})
        dump(args.output / (mode + "_curve.json"), curve)
        usable = y >= 0
        report_modes[mode] = {"checkpoint": outputs[mode], "train_metrics": {
            str(threshold): metrics(y[usable], probabilities[usable], threshold)
            for threshold in RECIPE["thresholds"]}, "runtime_probability_max_abs_error": max(errors),
            "last_train_loss": curve[-1]["train_loss"], "epochs": len(curve)}
    (args.output / "train_predictions.jsonl").write_text("".join(json.dumps(row)+"\n" for row in prediction_rows))
    report = {"manifest": identity(args.manifest), "source_commit": plan["source_commit"],
        "recipe": RECIPE, "models": outputs, "by_mode": report_modes,
        "training_opened_validation": False, "validation_used_for_early_stop": False,
        "validation_used_for_threshold_selection": False,
        "train_predictions": identity(args.output / "train_predictions.jsonl"),
        "runtime_admission": False, "qualification": "development fit; independent confirmation absent"}
    dump(args.output / "training_report.json", report)
    return {"report": identity(args.output / "training_report.json"), "models": outputs}


def evaluate(args):
    plan = read_plan(args)
    if identity(args.training_report)["sha256"] != args.training_report_sha:
        raise ValueError("final fixed model report changed before evaluation")
    train = json.loads(args.training_report.read_text())
    if train["manifest"]["sha256"] != args.manifest_sha:
        raise ValueError("model fitted under another registration")
    args.output.mkdir(parents=True, exist_ok=False)
    with np.load(pinned(plan["files"]["validation"]), allow_pickle=False) as data:
        raw, labels, modes, ids, groups, available = [np.array(data[key], copy=True)
            for key in ("x", "y", "mode", "sample_ids", "groups", "available")]
    # Exactly one prediction per row. Two preregistered threshold summaries
    # share that frozen prediction; neither chooses runtime admission.
    rows, by_mode = [], {}
    probabilities = np.zeros(len(raw))
    for mode in RECIPE["modes"]:
        model = pinned(train["models"][mode])
        for index in np.flatnonzero(modes == mode):
            outcome = infer(raw[index], available[index].tolist(), model, requested_mode=mode, profile=PROFILE)
            if outcome["status"] != "predicted" or outcome["stop_admitted"]:
                raise ValueError("no-stop development inference contract changed")
            probabilities[index] = outcome["p_satisfied"]
        usable = (modes == mode) & (labels >= 0)
        by_mode[mode] = {str(threshold): metrics(labels[usable], probabilities[usable], threshold)
                         for threshold in RECIPE["thresholds"]}
    for index in range(len(raw)):
        label = int(labels[index]) if labels[index] >= 0 else None
        rows.append({"sample_id": str(ids[index]), "raw_state_sha256": str(groups[index]),
            "split": "validation", "mode": str(modes[index]), "p_satisfied": float(probabilities[index]),
            "private_label_for_offline_analysis": label,
            "class_at_fixed_05": bool(probabilities[index] >= .5) if label is not None else None,
            "class_at_fixed_095": bool(probabilities[index] >= .95) if label is not None else None})
    path = args.output / "validation_predictions.jsonl"
    path.write_text("".join(json.dumps(row)+"\n" for row in rows))
    per_state = {state: {str(threshold): metrics(labels[mask], probabilities[mask], threshold)
                        for threshold in RECIPE["thresholds"]}
                 for state in sorted(set(groups.tolist()))
                 for mask in [(groups == state) & (labels >= 0)]}
    report = {"manifest": identity(args.manifest), "training_report": identity(args.training_report),
        "fixed_model_before_validation": True, "evaluation_passes": 1, "by_mode": by_mode,
        "per_raw_state": per_state, "predictions": identity(path),
        "unknown_rows_preserved": int((labels < 0).sum()), "validation_raw_states": len(set(groups)),
        "runtime_admission": False, "qualification": "one held-out development evaluation; not independent skill confirmation",
        "limitations": ["Both harness runs of each raw state are grouped; postblock frames remain correlated.",
                        "Frame Wilson intervals are descriptive only; six raw states do not establish 95% physical qualification.",
                        "Close verifier is still unmeasured at runtime; neither threshold is admitted."]}
    dump(args.output / "validation_report.json", report)
    return {"report": identity(args.output / "validation_report.json"), "by_mode": by_mode}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "fit", "evaluate"))
    parser.add_argument("--encoded-report", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha")
    parser.add_argument("--training-report", type=Path)
    parser.add_argument("--training-report-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"prepare": prepare, "fit": fit_train, "evaluate": evaluate}[args.stage](args)))


if __name__ == "__main__":
    main()
