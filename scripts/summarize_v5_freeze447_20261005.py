"""Recover the place442 report using explicit, hashed completed inputs."""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

from scripts.summarize_v5_A3_step750_20261003 import paired, summarize_group


def descriptor(path):
    path = Path(path)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.root / "results/harness_v5"
    prep = root / "placement442_model_regressions_20261004/preparation"
    prior_path = root / "completed385_A4_v327_full_CPU_20261004/preparation/index.json"
    prior = json.loads(prior_path.read_text())
    groups = {name: copy.deepcopy(value) for name, value in prior["groups"].items()
              if not value.get("baseline")}
    for model, job, directory in (("A3", 3419, "placement445_parallel_20261005"),
                                  ("A4", 3424, "placement444_parallel_20261005")):
        for batch in ("new41", "old40"):
            output = root / directory / f"{model}-N_job{job}"
            groups[f"{model}-place5-{batch}"] = {
                "manifest": descriptor(prep / f"{model}-N/{batch}.json"),
                "results": [{**descriptor(output / batch / "episodes.jsonl"), "format": "jsonl"}],
                "source_scope": "place440 commit 69045672, completed parallel replacement",
                "memory_scope": "none",
            }
            if model == "A3":
                groups[f"{model}-place5-{batch}"].update(
                    model_identity=str(output / "model_identity.json"),
                    expected_weight_sha256="b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb")
    index = {"groups": groups, "parent_index": descriptor(prior_path)}
    write_json(args.output / "index.json", index)
    summaries, indexed = {}, {}
    for name, group in groups.items():
        summaries[name], indexed[name] = summarize_group(group)
    comparisons = {
        "A4_persistence_to_place5_old40": paired(indexed["A4-N"], indexed["A4-place5-old40"]),
        "A4_motion327_to_place5_old40": paired(indexed["A4-N-motion327-old40"], indexed["A4-place5-old40"]),
        "A4_motion327_to_place5_new41": paired(indexed["A4-N-motion327-new41"], indexed["A4-place5-new41"]),
    }
    original = root / "placement441_original_gate200_20261004/job3414"
    summary_path = original / "summary/summary.json"
    placement_path = original / "placement_report.json"
    summary = json.loads(summary_path.read_text())
    placement = json.loads(placement_path.read_text())
    by_relation = {}
    for relation in ("on", "in"):
        counts = Counter()
        for row in placement["records"]:
            if row["measurement"]["relation"] != relation or row["private_recorded_truth"] is None:
                continue
            truth, predicted = bool(row["private_recorded_truth"]), row["recomputed"]["v5"]
            cell = ("abstained_positive" if truth else "abstained_negative") if predicted is None else (
                "tp" if predicted and truth else "fp" if predicted else "fn" if truth else "tn")
            counts[cell] += 1
        positive_predictions = counts["tp"] + counts["fp"]
        actual_positive = counts["tp"] + counts["fn"] + counts["abstained_positive"]
        by_relation[relation] = {
            "counts": dict(counts),
            "precision": counts["tp"] / positive_predictions if positive_predictions else None,
            "recall_including_abstentions": counts["tp"] / actual_positive if actual_positive else None,
        }
    physical_pass = bool(summary["complete_protocol"] and summary["attempted"] == 200
                         and summary["physical_success"] >= 160)
    metric = placement["metrics"]["v5"]
    precision_pass = bool(metric["precision"] is not None and metric["precision"] >= .95
                          and all(v["precision"] is not None and v["precision"] >= .95
                                  for v in by_relation.values()))
    report = {
        "purpose": "complete_three_layer_development_evidence_not_a_behavior_freeze",
        "jobs": {"original": 3414, "A3": 3419, "A4": 3424, "failed_report_retained": 3423},
        "original": {"source": descriptor(summary_path), "physical_success": summary["physical_success"],
                     "attempted": summary["attempted"], "correct_finish_secondary": summary["correct_finish"],
                     "gate_metric": "official_physical_success", "gate_pass": physical_pass,
                     "by_suite": summary["by_suite"], "terminal_counts": summary["terminal_counts"]},
        "strict_placement_v5": {"source": descriptor(placement_path), **metric,
                                "by_relation": by_relation, "precision_gate_pass": precision_pass,
                                "unrecomputable_events": placement["unrecomputable_events"]},
        "groups": summaries, "comparisons": comparisons,
        "behavior_freeze_eligible": False,
        "freeze_blockers": ["strict precision below 0.95", "A4 old40 physical regression"],
        "index": descriptor(args.output / "index.json"), "script": descriptor(__file__),
    }
    write_json(args.output / "report.json", report)
    compact = {"original": report["original"], "strict_placement_v5": report["strict_placement_v5"],
               "groups": {k: {f: v[f] for f in ("recorded", "official_success", "complete", "wall_median_s")}
                          for k, v in summaries.items()},
               "comparisons": {k: {f: v[f] for f in ("cells", "success_delta_pp")}
                               for k, v in comparisons.items()},
               "behavior_freeze_eligible": False}
    write_json(args.output / "summary.json", compact)
    print(json.dumps(compact))


if __name__ == "__main__":
    main()
