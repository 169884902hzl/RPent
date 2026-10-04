"""Score saved pre-action states with v5; receipts are labels only.

This is a retrospective prediction diagnostic, not a claim that the original
runner logged online success probabilities. Choice probabilities are unused.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from robots.libero.v5_success_choice import success_payload


def auc(labels, scores):
    positive = np.array(scores)[np.array(labels) == 1]
    negative = np.array(scores)[np.array(labels) == 0]
    if not len(positive) or not len(negative):
        return None
    return float(((positive[:, None] > negative).sum() + .5 * (positive[:, None] == negative).sum()) / (len(positive) * len(negative)))


def metrics(rows):
    labels = np.array([row["actual_success"] for row in rows])
    scores = np.array([row["p_success"] for row in rows])
    bins = []
    for index in range(10):
        included = (scores >= index / 10) & ((scores < (index + 1) / 10) if index < 9 else (scores <= 1))
        bins.append({"lower": index / 10, "upper": (index + 1) / 10, "count": int(included.sum()),
                     "mean_probability": float(scores[included].mean()) if included.any() else None,
                     "actual_success_rate": float(labels[included].mean()) if included.any() else None})
    return {"count": len(rows), "positives": int(labels.sum()), "negatives": int(len(rows) - labels.sum()),
            "AUROC": auc(labels, scores), "Brier": float(((scores - labels) ** 2).mean()) if len(rows) else None,
            "ECE10": sum(b["count"] / max(1, len(rows)) * abs(b["mean_probability"] - b["actual_success_rate"])
                         for b in bins if b["count"]), "reliability_bins": bins}


def outcome(event):
    receipt = event["receipt"]
    tool = receipt.get("tool")
    if tool not in ("grasp", "regrasp_restage", "place", "adjust_place", "articulate"):
        return None, "nonphysical_or_no_verifiable_success_check"
    if receipt.get("verification") == "execution_error":
        return 0, "execution_error"
    field = "grasp_verified" if tool in ("grasp", "regrasp_restage") else "place_verified" if tool in ("place", "adjust_place") else "articulate_verified"
    value = receipt.get(field)
    return (int(value), field) if isinstance(value, bool) else (None, "unknown_or_unverified")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with urlopen(args.endpoint.rstrip("/") + "/health", timeout=20) as response:
        identity = json.load(response)
    if identity["revision"] != args.expected_revision:
        raise ValueError("model identity differs from frozen v5")
    (args.output / "model_identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    kept, excluded, sources = [], Counter(), []
    with (args.output / "predictions.jsonl").open("x") as predictions, (args.output / "excluded.jsonl").open("x") as rejected:
        for episode in (json.loads(line) for line in args.ledger.read_text().splitlines()):
            path = Path(episode["output_dir"]) / "choices.jsonl"
            sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            for event in (json.loads(line) for line in path.read_text().splitlines()):
                actual, judge = outcome(event)
                if actual is None:
                    excluded[judge] += 1
                    continue
                # Only the saved pre-state and the selected action are model
                # input. Outcome, receipt and post-state are written separately.
                payload = success_payload(event["request"]["context"], event["selected"])
                request = Request(args.endpoint.rstrip("/") + "/v1/systemone", data=json.dumps(payload, ensure_ascii=False).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
                started = time.perf_counter()
                try:
                    with urlopen(request, timeout=180) as response:
                        reply = json.load(response)
                except HTTPError as error:
                    body = error.read().decode()
                    rejected.write(json.dumps({"episode": episode["episode"], "decision": event["decision"],
                                               "http_status": error.code, "error": body}) + "\n")
                    rejected.flush()
                    excluded[f"HTTP{error.code}"] += 1
                    continue
                probability = float(reply["answers"]["success"]["probabilities"]["C1"])
                if not np.isfinite(probability) or not 0 <= probability <= 1:
                    raise ValueError("invalid probability")
                row = {"episode": episode["episode"], "decision": event["decision"], "tool": event["receipt"]["tool"],
                       "task_family": episode["episode"]["suite"], "selected": event["selected"],
                       "request": payload, "response": reply, "p_success": probability,
                       "actual_success": actual, "judge": judge, "receipt": event["receipt"],
                       "http_s": time.perf_counter() - started, "source": str(path),
                       "prediction_mode": "retrospective_saved_preaction_state"}
                predictions.write(json.dumps(row) + "\n")
                predictions.flush()
                kept.append(row)
    families, tools, episodes = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in kept:
        families[row["task_family"]].append(row)
        tools[row["tool"]].append(row)
        episodes[json.dumps(row["episode"], sort_keys=True)].append(row)
    rng = random.Random(360)
    keys = list(episodes)
    bootstrap = []
    for _ in range(1000):
        sample = [row for key in rng.choices(keys, k=len(keys)) for row in episodes[key]] if keys else []
        score = auc([row["actual_success"] for row in sample], [row["p_success"] for row in sample])
        if score is not None:
            bootstrap.append(score)
    interval = np.quantile(bootstrap, [.025, .975]).tolist() if bootstrap else None
    report = {"prediction_mode": "retrospective_saved_preaction_state", "labels_never_in_model_input": True,
              "selection_probabilities_used_as_success_probability": False, "model_identity": identity,
              "total": metrics(kept), "by_family": {k: metrics(v) for k, v in families.items()},
              "by_tool": {k: metrics(v) for k, v in tools.items()}, "episode_bootstrap_95CI": interval,
              "bootstrap_replicates": len(bootstrap), "excluded": dict(excluded), "sources": sources,
              "top3_experiment_supported": interval is not None and interval[0] > .5,
              "new_training_rows": 0}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"total": report["total"], "CI": interval, "excluded": dict(excluded)}))


if __name__ == "__main__":
    main()
