"""Train a small RGB-D/proprio endpoint baseline on raw-state-separated data."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from public_temporal_verifier import identity


def metrics(labels, probabilities):
    predicted = probabilities >= .5
    tp, fp = int(((labels == 1) & predicted).sum()), int(((labels == 0) & predicted).sum())
    fn, tn = int(((labels == 1) & ~predicted).sum()), int(((labels == 0) & ~predicted).sum())
    positive, negative = probabilities[labels == 1], probabilities[labels == 0]
    auc = float(((positive[:, None] > negative[None, :]).sum() + .5 * (positive[:, None] == negative[None, :]).sum()) / (len(positive) * len(negative))) if len(positive) and len(negative) else None
    bins = []
    for lower in np.arange(0, 1, .1):
        mask = (probabilities >= lower) & (probabilities < lower + .1)
        if mask.any():
            bins.append({"lower": float(lower), "count": int(mask.sum()), "predicted_mean": float(probabilities[mask].mean()), "actual_rate": float(labels[mask].mean())})
    return {"rows": len(labels), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": float((predicted == labels).mean()), "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None, "auroc": auc,
        "brier": float(np.mean((probabilities - labels) ** 2)), "calibration_bins": bins,
        "positive_rate": float(labels.mean()), "fixed_classifier_threshold": .5}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(4); torch.manual_seed(577)
    with np.load(args.dataset / "public_features.npz", allow_pickle=False) as z:
        features, splits = z["features"], z["splits"]
    with np.load(args.dataset / "private_training_labels.npz", allow_pickle=False) as z:
        targets = z["targets"]
    train, val = (splits == "train") & (targets >= 0), (splits == "validation") & (targets >= 0)
    mean = features[train].mean(axis=0); scale = features[train].std(axis=0); scale[scale < .02] = 1
    x = torch.from_numpy((features - mean) / scale)
    y = torch.from_numpy(targets.astype(np.float32))
    model = torch.nn.Sequential(torch.nn.Linear(features.shape[1], 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.03)
    criterion = torch.nn.BCEWithLogitsLoss()
    curve = []; best = float("inf"); best_state = None; stale = 0; stopped = False
    for epoch in range(1, 301):
        model.train(); optimizer.zero_grad(); loss = criterion(model(x[train]).ravel(), y[train]); loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad():
            vl = float(criterion(model(x[val]).ravel(), y[val]))
        curve.append({"epoch": epoch, "train_loss": float(loss.detach()), "validation_loss": vl})
        if vl < best - .0001:
            best, best_epoch = vl, epoch; best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}; stale = 0
        else:
            stale += 1
        if stale >= 30:
            stopped = True; break
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad():
        probabilities = torch.sigmoid(model(x).ravel()).numpy()
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output / "temporal_mlp32.npz"
    np.savez_compressed(checkpoint, mean=mean, scale=scale, hidden_weight=model[0].weight.detach().numpy(),
        hidden_bias=model[0].bias.detach().numpy(), output_weight=model[2].weight.detach().numpy(), output_bias=model[2].bias.detach().numpy())
    rows = [json.loads(line) for line in (args.dataset / "public_samples.jsonl").read_text().splitlines()]
    predictions = [{"sample_id": r["sample_id"], "raw_state_sha256": r["raw_state_sha256"], "split": r["split"],
        "method": r["method"], "p_satisfied": float(p), "private_label_for_offline_analysis": None if y < 0 else int(y)} for r, p, y in zip(rows, probabilities, targets)]
    (args.output / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in predictions))
    (args.output / "training_curve.jsonl").write_text("".join(json.dumps(r) + "\n" for r in curve))
    report = {"model": "dual-camera RGB-D before+three frames and robot motion MLP32", "device": "cpu", "seed": 577,
        "epochs": len(curve), "best_epoch": best_epoch, "early_stop_patience": 30, "early_stopped": stopped,
        "train": metrics(targets[train], probabilities[train]), "validation": metrics(targets[val], probabilities[val]),
        "per_raw_state": {key: metrics(targets[m], probabilities[m]) for key in sorted({r["raw_state_sha256"] for r in rows})
            for m in [np.asarray([r["raw_state_sha256"] == key for r in rows]) & (targets >= 0)]},
        "checkpoint": identity(checkpoint), "stop_admitted": False, "qualification": "five selection states only; no confirmation endpoint test",
        "endpoint_unobstructed_data_missing": True, "dataset_report": identity(args.dataset / "dataset_report.json")}
    (args.output / "training_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "per_raw_state"}))


if __name__ == "__main__":
    main()
