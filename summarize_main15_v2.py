"""Summarize the original v2 episodes and the non-overlapping Jev completion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import statistics
from collections import Counter
from pathlib import Path


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--classifier", type=Path, default=Path("classify_results.py"))
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    module_spec = importlib.util.spec_from_file_location("episode_classifier", args.classifier)
    classifier = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(classifier)
    records = []
    videos = []
    missing = []
    for provider in ("dagger2323", "qwen4b", "jev"):
        for suite in ("libero_spatial_swap", "libero_object_swap"):
            for task in range(10):
                relative = Path(provider) / suite / f"task_{task}_seed_0" / "result.json"
                matches = [root / relative for root in args.roots if (root / relative).is_file()]
                if not matches:
                    missing.append(str(relative))
                    continue
                if len(matches) != 1:
                    raise ValueError(f"Overlapping completed episodes: {matches}")
                result_path = matches[0]
                record = classifier.classify(result_path)
                expected = (provider, suite, task, 0, 15)
                actual = tuple(record.get(key) for key in ("provider", "suite", "task", "seed", "max_decisions"))
                if actual != expected:
                    raise ValueError(f"Episode identity or budget mismatch: {result_path}: {actual}")
                trace_path = result_path.with_name("choices.jsonl")
                trace = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
                readonly = Counter(row["action"]["tool"] for row in trace
                                   if row["action"]["tool"] in {"segment", "back_project"})
                readonly_candidates = sum(candidate["tool"] in {"segment", "back_project"}
                                          for row in trace for candidate in row["candidates"])
                video_path = result_path.with_name("episode.mp4")
                record.update({
                    "result_path": str(result_path),
                    "result_sha256": digest(result_path),
                    "trace": str(trace_path),
                    "trace_sha256": digest(trace_path),
                    "video": str(video_path.resolve()),
                    "readonly_selections": dict(readonly),
                    "readonly_candidate_count": readonly_candidates,
                    "actual_models": dict(Counter(stage.get("model") for row in trace for stage in row["stages"])),
                    "action_sequence": [row["action"] for row in trace],
                })
                records.append(record)
                videos.append({
                    "provider": provider, "suite": suite, "task": task, "seed": 0,
                    "path": str(video_path.resolve()),
                    "bytes": video_path.stat().st_size if video_path.is_file() else None,
                    "sha256": digest(video_path) if video_path.is_file() else None,
                })
    if missing and not args.allow_incomplete:
        raise ValueError(f"Missing {len(missing)} episodes: {missing}")
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for provider in ("dagger2323", "qwen4b", "jev"):
        for suite in ("libero_spatial_swap", "libero_object_swap"):
            subset = [row for row in records if row["provider"] == provider and row["suite"] == suite]
            summary = {
                "provider": provider, "suite": suite, "episodes": len(subset),
                "successes": sum(bool(row["official_success"]) for row in subset),
                "failure_categories": dict(Counter(row["failure_category"] for row in subset)),
                "budget_cap_reached": sum(row.get("budget_cap_reached", False) for row in subset),
                "readonly_selections": sum(sum(row["readonly_selections"].values()) for row in subset),
                "readonly_candidate_count": sum(row["readonly_candidate_count"] for row in subset),
                "actual_models": dict(sum((Counter(row["actual_models"]) for row in subset), Counter())),
            }
            for metric in ("model_inference", "harness_total"):
                values = [value for row in subset for value in row[f"{metric}_latency_s"]]
                summary[f"{metric}_steps"] = len(values)
                summary[f"{metric}_mean_s"] = statistics.mean(values) if values else None
            summaries.append(summary)
    summary_document = {
        "condition": "Main15-v2 development; does not replace Main15-v1",
        "harness_commit": "f037752003c80bdc818f540f82b6046d8ed304e9",
        "classifier_sha256": digest(args.classifier),
        "classifier_path": str(args.classifier),
        "roots": [str(root) for root in args.roots],
        "missing": missing, "groups": summaries,
    }
    (args.output / "summary.json").write_text(json.dumps(summary_document, ensure_ascii=False, indent=2) + "\n")
    (args.output / "classified.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records))
    with (args.output / "video_index.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["provider", "suite", "task", "seed", "path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(videos)
    lines = ["# Main15-v2 development episode audit", "",
             "Local Qwen times are server computation; Jev times are official API HTTP round trips.", "",
             "| Provider | Suite | Task | Success | Decisions | Model time/step (s) | Harness/step (s) | Failure | Budget cap | Read-only selections | Video |",
             "| --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- | ---: | --- |"]
    for row in records:
        lines.append(
            f"| {row['provider']} | {row['suite']} | {row['task']} | {row['official_success']} | "
            f"{row['decisions']} | {row['mean_model_inference_latency_s']:.3f} | "
            f"{row['mean_harness_total_latency_s']:.3f} | {row['failure_category']} | "
            f"{row.get('budget_cap_reached', False)} | {sum(row['readonly_selections'].values())} | "
            f"{row['video']} |"
        )
    (args.output / "episode_audit.md").write_text("\n".join(lines) + "\n")
    video_lines = ["# Main15-v2 development videos", "",
                   "Video binaries remain on node02; paths and checksums index the complete recordings.", "",
                   "| Provider | Suite | Task | Video | SHA256 |", "| --- | --- | ---: | --- | --- |"]
    for video in videos:
        video_lines.append(f"| {video['provider']} | {video['suite']} | {video['task']} | {video['path']} | {video['sha256']} |")
    (args.output / "video_index.md").write_text("\n".join(video_lines) + "\n")
    print(json.dumps(summary_document, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
