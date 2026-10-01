"""Audit an explicit partial collection index; never discover artifact files."""

import argparse
import collections
import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def request_hash(request):
    return hashlib.sha256(json.dumps(request, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    index = json.loads(args.index.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    files, episodes, tasks, failures, pending = [], [], {}, [], []
    tokens, signatures, questions = [], set(), collections.Counter()
    counts = collections.Counter()
    elapsed = 0.0
    timed_rows = 0
    runtime_rows = []
    for shard in index["shards"]:
        ledger = Path(shard["output"]) / "episodes.jsonl"
        if not ledger.exists():
            pending.append(str(ledger))
            continue
        for line in ledger.read_text().splitlines():
            item = json.loads(line)
            e = item["episode"]
            assert 10 <= e["seed"] < 40, e
            identity = (e["suite"], e["task"], e["seed"])
            if any(tuple(x["identity"]) == identity for x in episodes):
                raise ValueError(f"duplicate attempted episode: {identity}")
            episode = Path(item["output_dir"])
            manifest = json.loads((episode / "training_manifest.json").read_text())
            result = item["result"]
            elapsed += result.get("wall_s", 0)
            episodes.append({"identity": identity, "output": str(episode), "result": result,
                             "manifest_sha256": sha(episode / "training_manifest.json")})
            if not result.get("correct_finish"):
                failures.append({"identity": identity, "category": result.get("termination_category"),
                                 "detail": result.get("termination_detail", result.get("error"))})
            task = tasks.setdefault(f"{e['suite']}/{e['task']}", collections.Counter())
            task["attempted"] += 1
            task["correct_finish"] += int(result.get("correct_finish", False))
            live = {}
            choice_file = episode / "choices.jsonl"
            if choice_file.exists():
                for raw in choice_file.read_text().splitlines():
                    decision = json.loads(raw)
                    req = decision["request"]
                    wire = {"state": req["context"], "questions": {"action": {
                        "type": "choice", "instructions": req["instruction"],
                        "criteria": {f"C{i}": text for i, text in enumerate(req["options"])}}}}
                    live[decision["decision"]] = wire
            for bucket, desc in manifest["files"].items():
                path = Path(desc["path"])
                assert sha(path) == desc["sha256"], path
                lines = path.read_text().splitlines()
                assert len(lines) == desc["rows"], path
                files.append({"episode": identity, "bucket": bucket, **desc})
                counts[bucket] += len(lines)
                task[bucket] += len(lines)
                if bucket == "train" and shard.get("throughput_count", True):
                    timed_rows += len(lines)
                if bucket not in ("train", "auxiliary"):
                    continue
                for raw in lines:
                    row = json.loads(raw)
                    state = row["request"]["state"]
                    assert row["schema_version"] == "entities-plan-receipt/3.1"
                    assert row["judge"] in ("physics_branch", "measured_predicate", "plan_oracle", "program_termination")
                    assert row["domain"] == "libero" and row["init_state_index"] == e["seed"]
                    assert row["init_state_sha256"] == e["init_state_sha256"]
                    assert row["prompt_tokens"] <= 3072 and row["acceptable_actions"]
                    assert "sim_truth" not in state and "BDDL" not in state
                    assert not re.search(r"\b(?:obj_|zone_)", state)
                    assert set(re.findall(r"\b[a-z][a-z_]*_\d+\b", state)) <= {"yaw_90"}
                    assert all("src=perception" in s for s in state.splitlines() if s.startswith("e "))
                    codes = set(row["request"]["questions"]["action"]["criteria"])
                    assert set(row["acceptable_actions"]) <= set(row["evaluated_actions"]) <= codes
                    assert set(row["unknown_actions"]) == codes - set(row["evaluated_actions"])
                    assert row["source_hashes"] == manifest["source_hashes"]
                    tokens.append(row["prompt_tokens"])
                    questions[row["question_type"]] += 1
                    signatures.add((row["question_type"], request_hash(row["request"])))
                    if bucket == "train":
                        assert row["request"] == live[row["step"]], (identity, row["step"])
                        runtime_rows.append({"scene_id": row["scene_id"], "stage": row["stage"],
                                             "step": row["step"], "request": live[row["step"]]})
    runtime_path = args.output / "runtime_requests.jsonl"
    runtime_path.write_text("".join(json.dumps(row) + "\n" for row in runtime_rows))
    total = counts["train"] + counts["auxiliary"]
    measured_wall = time.time() - index["started_at_epoch"] if index.get("started_at_epoch") else None
    task_output = {name: dict(count) | {"mean_valid_next_skill_rows_per_episode": count["train"] / count["attempted"]}
                   for name, count in tasks.items()}
    report = {"purpose": "audited original-task partial collection; not full SFT admission",
              "input_index": str(args.index), "input_index_sha256": sha(args.index),
              "status": "PASS_PARTIAL" if total else "NO_VALID_ROWS",
              "attempted_episodes": len(episodes), "correct_finish": sum(t["correct_finish"] for t in tasks.values()),
              "counts": dict(counts), "questions": dict(questions), "unique_question_requests": len(signatures),
              "by_task": task_output, "failures": failures, "pending_ledgers": pending, "files": files,
              "runtime_requests": {"path": str(runtime_path), "rows": len(runtime_rows), "sha256": sha(runtime_path)},
              "token_p95": float(np.percentile(tokens, 95)) if tokens else None,
              "token_max": max(tokens) if tokens else None,
              "episode_cpu_gpu_wall_sum_s": elapsed,
              "sequential_train_rows_per_hour": counts["train"] * 3600 / elapsed if elapsed else None,
              "cohort_wall_s_including_warmup": measured_wall,
              "completed_cohort_next_skill_rows": timed_rows,
              "completed_cohort_rows_per_hour": timed_rows * 3600 / measured_wall if measured_wall else None,
              "all_checked_next_skill_requests_match_runtime": True,
              "excluded_init_overlap": 0,
              "negative_bucket_note": "Premature finish rows point to the same decision source; not added independent states.",
              "counterfactual_status": index.get("counterfactual_status", "pending")}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "episodes.json").write_text(json.dumps(episodes, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("files", "by_task", "failures")}))
    if not total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
