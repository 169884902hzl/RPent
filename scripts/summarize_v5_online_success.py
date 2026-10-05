"""Join recorded pre-action success predictions to their executed outcomes."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

import numpy as np

from scripts.diagnose_v5_preaction_success import auc, metrics, outcome
from robots.libero.v5_success_choice import success_payload


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def executed_prediction(event):
    """Refuse a changed candidate, different context, or retrospective score."""
    diagnostic = event["answer"].get("pre_action_success_diagnostic")
    if diagnostic is None:
        return None, "no_online_prediction"
    context, selected = event["request"]["context"], event["selected"]
    if (diagnostic["phase"] != "before_physical_branches_and_execution"
            or diagnostic["selection_changed"] is not False
            or diagnostic["candidate"] != selected
            or diagnostic["context_sha256"] != hashlib.sha256(context.encode()).hexdigest()
            or event["candidates"][diagnostic["candidate_index"]] != selected
            or int(event["answer"]["selected"]) != diagnostic["candidate_index"]):
        raise ValueError("online prediction does not match the selected action and pre-state")
    prediction = diagnostic["prediction"]
    if prediction["request"] != success_payload(context, selected):
        raise ValueError("online success request differs from the recorded pre-state/action")
    probability = float(diagnostic["p_success"])
    saved_probability = float(prediction["response"]["answers"]["success"]["probabilities"]["C1"])
    if probability != saved_probability or not np.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("online success probability differs from response")
    actual, judge = outcome(event)
    if actual is None:
        return None, judge
    return {"decision": event["decision"], "selected": selected,
            "tool": event["receipt"]["tool"], "p_success": probability,
            "actual_success": actual, "judge": judge,
            "context_sha256": diagnostic["context_sha256"],
            "http_round_trip_s": prediction["http_round_trip_s"],
            "model_inference_s": prediction.get("model_inference_s"),
            "receipt": event["receipt"]}, None


def summarize(rows, seed):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["episode_key"]].append(row)
    keys, rng, scores = list(grouped), random.Random(seed), []
    for _ in range(1000):
        sample = [r for key in rng.choices(keys, k=len(keys)) for r in grouped[key]] if keys else []
        score = auc([r["actual_success"] for r in sample], [r["p_success"] for r in sample])
        if score is not None:
            scores.append(score)
    high = [r for r in rows if r["p_success"] >= .9]
    measured = metrics(rows)
    if not rows:
        measured["ECE10"] = None
    return {**measured, "episode_count": len(keys),
            "episode_bootstrap_AUROC_95CI": np.quantile(scores, [.025, .975]).tolist() if scores else None,
            "bootstrap_valid_replicates": len(scores), "bootstrap_seed": seed,
            "high_confidence_at_least_0_9": len(high),
            "high_confidence_failures": sum(not r["actual_success"] for r in high),
            "high_confidence_error_rate": sum(not r["actual_success"] for r in high) / len(high) if high else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=471)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows, sources, excluded, seen = [], [], Counter(), set()
    for ledger in args.ledger:
        sources.append({"path": str(ledger), "sha256": sha(ledger)})
        for line in ledger.read_text().splitlines():
            episode = json.loads(line)
            trace = Path(episode["output_dir"]) / "choices.jsonl"
            if trace in seen:
                raise ValueError("duplicate physical source episode")
            seen.add(trace)
            sources.append({"path": str(trace), "sha256": sha(trace)})
            identity = json.dumps(episode.get("episode", episode.get("case", {}).get("episode")), sort_keys=True)
            family = (episode.get("episode") or episode.get("case", {}).get("episode"))["suite"]
            for event in map(json.loads, trace.read_text().splitlines()):
                row, reason = executed_prediction(event)
                if reason:
                    excluded[reason] += 1
                    continue
                rows.append({**row, "episode_key": identity, "task_family": family, "source": str(trace)})
    families, tools = defaultdict(list), defaultdict(list)
    for row in rows:
        families[row["task_family"]].append(row)
        tools[row["tool"]].append(row)
    report = {"prediction_mode": "recorded_online_before_action",
              "total": summarize(rows, args.bootstrap_seed),
              "by_family": {k: summarize(v, args.bootstrap_seed) for k, v in families.items()},
              "by_tool": {k: summarize(v, args.bootstrap_seed) for k, v in tools.items()},
              "excluded": dict(excluded), "sources": sources, "script_sha256": sha(__file__),
              "labels": "saved measured receipt success checks; unverified/unknown remain excluded",
              "selection_probabilities_used_as_success_probabilities": False,
              "top3_behavior_or_freeze_enabled": False, "new_model_calls": 0, "new_training_rows": 0}
    (args.output / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"total": report["total"], "excluded": report["excluded"]}))


if __name__ == "__main__":
    main()
