"""Resume only explicitly registered, unattempted interim expert or A3 episodes."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def ref(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_pinned(item):
    path = Path(item["path"])
    if not path.is_absolute() or ref(path)["sha256"] != item["sha256"]:
        raise ValueError(f"Pinned input changed: {path}")
    return path


def key(episode):
    return episode["suite"], int(episode["task"]), int(episode["seed"])


def a3_failure_group(result):
    """Separate evidenced code faults from physical results without editing them."""
    error = str(result.get("error", ""))
    if "not JSON serializable" in error:
        return "infrastructure", "code_serialization"
    if result.get("infrastructure_failure"):
        return "infrastructure", "reported_infrastructure_failure"
    if result.get("status") in ("startup", "startup_error") or result.get("termination_category") == "startup_error":
        return "infrastructure", "startup_error"
    if result.get("official_success") is True:
        return "functional", "success"
    return "functional", result.get("termination_category") or "unclassified"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-index", type=Path, required=True)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--ledger-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cohort", choices=("expert", "A3-N"), default="expert")
    args = parser.parse_args()
    parent = json.loads(args.parent_index.read_text())
    source = json.loads(args.source_plan.read_text())["source_snapshot"]
    ledger_index = json.loads(args.ledger_index.read_text())
    if ledger_index["all_running_shards_terminal"] is not True:
        raise ValueError("Wait for the current episodes' natural boundaries before computing remainder")
    plans = [json.loads(read_pinned(item).read_text()) for item in parent["files"]
             if Path(item["path"]).name.startswith(args.cohort + "_part")]
    episodes = [episode for plan in plans for episode in plan["episodes"]]
    expected = {key(episode) for episode in episodes}
    expected_count = 200 if args.cohort == "expert" else 80
    if len(episodes) != expected_count or len(expected) != expected_count:
        raise ValueError(f"Expected the original registered {expected_count} unique {args.cohort} episodes")
    attempted = set()
    preserved_rows = []
    for item in ledger_index["files"]:
        for line in read_pinned(item).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            identity = key(row["episode"])
            if identity not in expected or identity in attempted:
                raise ValueError(f"Unexpected or duplicate preserved interim episode: {identity}")
            attempted.add(identity)
            if args.cohort == "A3-N":
                group, category = a3_failure_group(row["result"])
                preserved_rows.append({"episode": row["episode"], "output_dir": row["output_dir"],
                    "ledger": item, "group": group, "category": category,
                    "original_result": row["result"],
                    "original_infrastructure_flag": row["result"].get("infrastructure_failure"),
                    "accounting_only_original_result_unchanged": True})
    if args.cohort == "A3-N":
        for started in ledger_index.get("started_without_ledger", []):
            identity = key(started["episode"])
            if identity not in expected or identity in attempted:
                raise ValueError(f"Unexpected or duplicated off-ledger attempt: {identity}")
            if not Path(started["output_dir"]).is_dir():
                raise ValueError("Off-ledger attempt must have its explicit existing output directory")
            for item in started.get("files", []):
                read_pinned(item)
            attempted.add(identity)
            preserved_rows.append({**started, "group": "unresolved_attempt",
                "category": "started_without_terminal_ledger", "model_score": None})
    remainder = [episode for episode in episodes if key(episode) not in attempted]
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError("Keep the prior preparation immutable")
    out.mkdir(parents=True)
    template = plans[0]
    files = []
    for part in range(8):
        payload = {**template, "source_path": source["path"], "source_commit": source["commit"],
                   "episodes": remainder[part::8], "preserved_attempts": len(attempted),
                   "resume_policy": "Unattempted episodes only; completed failures remain failures"}
        if not payload["episodes"]:
            raise ValueError("Eight nonempty resume shards required by this launcher")
        path = out / f"{args.cohort}_part{part}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        files.append(ref(path))
    source_root = Path(source["path"])
    for item in [*source["files"], source["archive"]]:
        read_pinned(item)
    index = {**parent, "files": files, "source_path": source["path"],
             "source_commit": source["commit"], "source_snapshot": source,
             "batch_runner": ref(source_root / "v5_batch_eval.py"),
             "launcher": ref(source_root / "scripts/run_v5_interim574.sbatch"),
             "runtime_supplement": [ref(source_root / "typed_choice_eval.py")],
             "planned": {args.cohort: len(remainder)},
             "preserved_attempts": len(attempted), "full_cohort_unique_episodes": expected_count,
             "references": [*parent["references"], ref(args.parent_index), ref(args.source_plan),
                            ref(args.ledger_index), *ledger_index["files"]]}
    if args.cohort == "A3-N":
        counts = Counter((row["group"], row["category"]) for row in preserved_rows)
        by_suite = defaultdict(Counter)
        for row in preserved_rows:
            by_suite[row["episode"]["suite"]][row["group"] + "/" + row["category"]] += 1
        remainder_counts = Counter((episode["suite"], episode["seed"]) for episode in remainder)
        audit = {"cohort": "A3-N", "registered": expected_count, "preserved_attempts": len(attempted),
            "ledger_attempts": len(preserved_rows) - len(ledger_index.get("started_without_ledger", [])),
            "off_ledger_attempts": len(ledger_index.get("started_without_ledger", [])),
            "remaining": len(remainder), "counts": {group + "/" + category: count
                for (group, category), count in sorted(counts.items())},
            "by_suite": {suite: dict(count) for suite, count in sorted(by_suite.items())},
            "remainder_by_suite_seed": [{"suite": suite, "seed": seed, "episodes": count}
                for (suite, seed), count in sorted(remainder_counts.items())],
            "preserved_rows": preserved_rows, "unattempted_episodes": remainder,
            "complete_cohort_model_score": None,
            "reason": "partial developer accounting; infrastructure rows are not model results",
            "attempted_and_remaining_overlap": 0,
            "all_original_records_retained": True, "GPU_submitted": False}
        audit_path = out / "preserved_attempt_audit.json"
        audit_path.write_text(json.dumps(audit, indent=2) + "\n")
        index.update(preserved_attempt_audit=ref(audit_path),
            accounting_only_original_results_unchanged=True,
            all_previous_jobs_terminal_or_held=ledger_index.get("all_previous_jobs_terminal_or_held"),
            previous_held_jobs_must_not_be_released_with_resume=True,
            generator=ref(__file__))
    (out / "manifest.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"index": ref(out / "manifest.json"), "preserved": len(attempted),
                      "remaining": len(remainder), "shards": len(files)}))


if __name__ == "__main__":
    main()
