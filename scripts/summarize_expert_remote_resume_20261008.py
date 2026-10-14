#!/usr/bin/env python3
"""Summarize the explicit expert resume chain without replacing old records."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def key(episode):
    return episode["suite"], int(episode["task"]), int(episode["seed"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(success, total):
    if not total:
        return None
    z = 1.959963984540054
    p = success / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [centre - radius, centre + radius]


def read_ledger(path):
    records = []
    for line, text in enumerate(path.read_text().splitlines(), 1):
        if text.strip():
            records.append({"ledger": {"path": str(path), "sha256": sha(path)},
                            "line": line, **json.loads(text)})
    return records


def execution_metrics(row):
    path = Path(row["output_dir"]) / "choices.jsonl"
    traces = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    attempts = Counter()
    verification = defaultdict(Counter)
    selected_counts = Counter()
    previous, run, longest = None, 0, 0
    measured_receipts = 0
    for trace in traces:
        receipt = trace.get("receipt") or {}
        tool = receipt.get("tool", "missing")
        attempts[tool] += 1
        verification[tool][receipt.get("verification", "missing")] += 1
        selected = trace.get("selected")
        selected_counts[selected] += 1
        run = run + 1 if selected == previous else 1
        longest = max(longest, run)
        previous = selected
        measured_receipts += isinstance(receipt.get("measurement"), dict)
    return {
        "episode": row["episode"],
        "trace_path": str(path), "trace_sha256": sha(path),
        "decisions": len(traces),
        "attempts_by_skill": dict(attempts),
        "verification_by_skill": {key: dict(value) for key, value in verification.items()},
        "maximum_consecutive_same_action": longest,
        "maximum_same_action_total": max(selected_counts.values(), default=0),
        "measured_receipts": measured_receipts,
        "vla_subtask_attempts": attempts["vla_subtask"],
        "fusion": row["result"].get("fusion_measurements"),
        "wall_s": row["result"].get("wall_s"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation-root", type=Path, required=True)
    parser.add_argument("--startup-job", required=True)
    parser.add_argument("--formal-job", required=True)
    parser.add_argument("--retry-startup-job")
    parser.add_argument("--retry-formal-job")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_path = args.preparation_root / "ledger_audit.json"
    audit = json.loads(audit_path.read_text())
    expected = {(suite, task, seed)
                for suite in ("libero_spatial", "libero_object", "libero_goal", "libero_10")
                for task in range(10) for seed in range(5)}
    retry_manifest_path = args.preparation_root / "program_error_retry6/manifest.json"
    retry_manifest = json.loads(retry_manifest_path.read_text())
    allowed_retries = {key(episode) for part in retry_manifest["files"]
                       for episode in json.loads(Path(part["path"]).read_text())["episodes"]}
    root = Path("/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/expert")
    rows = list(audit["preserved_rows"])
    sources = [(root / "startup_preflight" / f"job{args.startup_job}" / "part0/probe/episodes.jsonl")]
    sources += sorted((root / f"job{args.formal_job}").glob("part*/probe/episodes.jsonl"))
    for path in sources:
        if path.exists():
            rows.extend(read_ledger(path))
    original = {}
    for row in rows:
        identity = key(row["episode"])
        if identity in original:
            raise ValueError(f"duplicate original identity: {identity}")
        if identity not in expected:
            raise ValueError(f"unregistered original identity: {identity}")
        original[identity] = row
    effective = dict(original)
    retry_rows = []
    if args.retry_startup_job:
        p = root / "startup_preflight" / f"job{args.retry_startup_job}" / "part0/probe/episodes.jsonl"
        if p.exists():
            retry_rows.extend(read_ledger(p))
    if args.retry_formal_job:
        for p in sorted((root / f"job{args.retry_formal_job}").glob("part*/probe/episodes.jsonl")):
            retry_rows.extend(read_ledger(p))
    seen_retries = set()
    for row in retry_rows:
        identity = key(row["episode"])
        if identity in seen_retries or not row["episode"].get("program_error_retry"):
            raise ValueError(f"invalid or duplicate program-error retry: {identity}")
        if identity not in allowed_retries:
            raise ValueError(f"unregistered program-error retry: {identity}")
        if identity not in original or not any(s in str(original[identity]["result"].get("error", ""))
                                                for s in ("StopIteration", " is not in list")):
            raise ValueError(f"retry lacks its original program-error record: {identity}")
        seen_retries.add(identity)
        effective[identity] = row
    by_suite = defaultdict(list)
    for identity, row in effective.items():
        by_suite[identity[0]].append(row)
    success = sum(row["result"].get("official_success") is True for row in effective.values())
    categories = Counter(row["result"].get("termination_category") or row["result"].get("status")
                         for row in effective.values())
    metrics = [execution_metrics(row) for row in effective.values()]
    attempts = Counter()
    verification = defaultdict(Counter)
    for record in metrics:
        attempts.update(record["attempts_by_skill"])
        for tool, counts in record["verification_by_skill"].items():
            verification[tool].update(counts)
    walls = [record["wall_s"] for record in metrics if isinstance(record["wall_s"], (float, int))]
    result = {
        "provenance": {
            "summarizer": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__))},
            "ledger_audit": {"path": str(audit_path), "sha256": sha(audit_path)},
            "retry_manifest": {"path": str(retry_manifest_path), "sha256": sha(retry_manifest_path)},
            "runtime_handoff": json.loads((args.preparation_root / "runtime_handoff.json").read_text()),
            "runtime_handoff_scope": "new resume and retry jobs only; preserved rows retain their own source hashes",
            "jobs": {"startup": args.startup_job, "formal": args.formal_job,
                     "retry_startup": args.retry_startup_job, "retry_formal": args.retry_formal_job},
        },
        "registered": 200,
        "original_closed": len(original),
        "pending_original": 200 - len(original),
        "pending_original_identities": [{"suite": suite, "task": task, "seed": seed}
                                        for suite, task, seed in sorted(expected - original.keys())],
        "one_time_program_retries_closed": len(retry_rows),
        "one_time_program_retries_pending": 6 - len(retry_rows),
        "raw_original_success": sum(row["result"].get("official_success") is True for row in original.values()),
        "raw_original_termination_categories": dict(Counter(
            row["result"].get("termination_category") or row["result"].get("status")
            for row in original.values())),
        "effective_official_physical_success": success,
        "effective_success_wilson95_closed": wilson(success, len(effective)),
        "correct_finish_secondary": sum(row["result"].get("correct_finish") is True for row in effective.values()),
        "categories": dict(categories),
        "by_suite": {suite: {"closed": len(suite_rows), "registered": 50,
                             "success": sum(r["result"].get("official_success") is True for r in suite_rows),
                             "wilson95_closed": wilson(sum(r["result"].get("official_success") is True for r in suite_rows), len(suite_rows))}
                     for suite, suite_rows in sorted(by_suite.items())},
        "complete": set(original) == expected and seen_retries == allowed_retries,
        "target_190_200_met": success >= 190 if set(original) == expected and seen_retries == allowed_retries else None,
        "target_kind": "internal reporting target",
        "all_original_results_retained": True,
        "median_wall_s": statistics.median(walls) if walls else None,
        "execution_aggregate": {
            "attempts_by_skill": dict(attempts),
            "verification_by_skill": {key: dict(value) for key, value in verification.items()},
            "maximum_consecutive_same_action": max((record["maximum_consecutive_same_action"] for record in metrics), default=0),
            "episodes_consecutive_same_action_ge20": sum(record["maximum_consecutive_same_action"] >= 20 for record in metrics),
            "episodes_total_same_action_ge20": sum(record["maximum_same_action_total"] >= 20 for record in metrics),
            "vla_subtask_attempts": attempts["vla_subtask"],
            "fusion_enabled_episodes": sum((record["fusion"] or {}).get("enabled") is True for record in metrics),
        },
        "episode_execution_metrics": metrics,
        "original_rows": list(original.values()),
        "program_error_retry_rows": retry_rows,
        "effective_rows": list(effective.values()),
        "non_program_failures": [r for r in effective.values()
                                 if r["result"].get("official_success") is not True
                                 and not any(s in str(r["result"].get("error", ""))
                                             for s in ("StopIteration", " is not in list"))],
    }
    if args.output.exists():
        raise SystemExit("preserve the previous summary; use a new output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in
                      ("provenance", "original_rows", "program_error_retry_rows", "effective_rows", "non_program_failures", "episode_execution_metrics", "pending_original_identities")}, indent=2))
    print("SHA256", sha(args.output))


if __name__ == "__main__":
    main()
