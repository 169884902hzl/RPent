"""Correct labels from explicit physical evidence; never overwrite raw shards."""

import argparse
import collections
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from robots.libero.v5_collection import accepted_branch, wire_request
from robots.libero.v5_state import Candidate
import shared_v5r_schema as shared


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--choice-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.manifest = args.manifest.resolve()
    args.output = args.output.resolve()
    from transformers import AutoTokenizer
    sys.path.insert(0, str(args.choice_package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(args.choice_package, local_files_only=True)
    source = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    counts = collections.Counter()
    by_task = collections.defaultdict(collections.Counter)
    train, rejected, runtime = [], [], []
    tokens, keys = [], set()
    live_by_file = {}
    for descriptor in source["files"]:
        if descriptor["bucket"] not in ("train", "zero_signal"):
            continue
        path = Path(descriptor["path"])
        if sha(path) != descriptor["sha256"]:
            raise ValueError(f"raw evidence changed: {path}")
        for line in path.read_text().splitlines():
            item = json.loads(line)
            raw = item if descriptor["bucket"] == "train" else item.get("row")
            if raw is None or not raw.get("label_evidence", {}).get("branches"):
                continue
            row = copy.deepcopy(raw)
            branches = row["label_evidence"]["branches"]
            primary = "C" + str(row["label_evidence"]["original_expert_selected"])
            assert branches[0]["code"] == primary
            codes = list(row["request"]["questions"]["action"]["criteria"])
            good, evaluated, changes = [], [], []
            for index, branch in enumerate(branches):
                tool = branch["action"].split("(", 1)[0]
                accepted = branch["accepted"]
                if tool == "finish":
                    accepted = bool(branch["before"]["done"])
                elif tool == "ask_help":
                    accepted = False if branch["before"]["done"] else None
                elif index == 0 and tool == "place":
                    accepted = accepted_branch(Candidate("place"), branch["receipt"], branch["before"], branch["after"])
                elif index > 0 and "robots/libero/v5_branch_state.py" not in row.get("source_hashes", row["source"]):
                    # These legacy alternatives restored qpos but not accumulated
                    # actuator commands. Their labels cannot be compared fairly.
                    accepted = None
                    counts["legacy_secondary_motion_masked_unknown"] += 1
                if accepted != branch["accepted"]:
                    changes.append({"code": branch["code"], "original": branch["accepted"], "corrected": accepted})
                if accepted is not None:
                    evaluated.append(branch["code"])
                    if accepted:
                        good.append(branch["code"])
            row.update(acceptable_actions=good, evaluated_actions=evaluated,
                       unknown_actions=[code for code in codes if code not in evaluated])
            row["label_correction"] = {"source_file": str(path), "source_file_sha256": descriptor["sha256"],
                                       "script_sha256": sha(__file__), "changes": changes,
                                       "rule": "physical progress independently verified; legacy secondary motion labels unknown"}
            key = (row["scene_id"], row["stage"], row["step"])
            if key in keys:
                raise ValueError(f"duplicate state: {key}")
            keys.add(key)
            counts["raw_decision_states"] += 1
            counts["labels_changed"] += bool(changes)
            task = by_task[f"{row['suite']}/{row['task_id']}"]
            task["raw_decision_states"] += 1
            if not good:
                rejected.append({"reason": "no_acceptable_verified_branch", "row": row})
                continue
            assert 10 <= row["init_state_index"] < 40
            assert row["judge"] == "physics_branch"
            _, prepared = shared.prepare_example(row, tokenizer, parallel_schema, limit=3072)
            row["prompt_tokens"] = len(prepared.full_ids[0])
            row["source_hashes"] = row.get("source_hashes", row["source"])
            row["runtime_source_sha256"] = row["source_hashes"]["robots/libero/v5_state.py"]
            row["source_key"] = {"request_hash": shared.digest(row["request"]), "scene": row["scene_id"], "stage": row["stage"], "step": row["step"]}
            choice_path = path.parent / "choices.jsonl"
            if choice_path not in live_by_file:
                live_by_file[choice_path] = {r["decision"]: r for r in map(json.loads, choice_path.read_text().splitlines())}
            actual = wire_request(live_by_file[choice_path][row["step"]]["request"])
            assert shared.request_bytes(actual) == shared.request_bytes(row["request"])
            assert row["prompt_tokens"] <= 3072
            train.append(row)
            runtime.append({"scene_id": row["scene_id"], "stage": row["stage"], "step": row["step"], "request": actual,
                            "source_file": str(choice_path), "source_file_sha256": sha(choice_path)})
            tokens.append(row["prompt_tokens"])
            task["selected_valid_next_skill"] += 1
            counts["recovered_raw_zero_signal"] += descriptor["bucket"] == "zero_signal"
    files = []
    for name, rows, bucket in (("train", train, "train"), ("rejected", rejected, "zero_signal")):
        path = args.output / (name + ".jsonl")
        path.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows))
        files.append({"path": str(path), "sha256": sha(path), "rows": len(rows), "bucket": bucket})
    files.extend(d for d in source["files"] if d["bucket"] == "auxiliary")
    runtime_path = args.output / "runtime_requests.jsonl"
    runtime_path.write_text("".join(json.dumps(row) + "\n" for row in runtime))
    report = {"purpose": "corrected training prefix pending independent native admission", "status": "PASS_LOCAL_REQUEST_REPLAY",
              "input_manifest": str(args.manifest), "input_manifest_sha256": sha(args.manifest),
              "source_script": str(Path(__file__).resolve()), "source_script_sha256": sha(__file__),
              "source_hashes": {str(args.manifest): sha(args.manifest)},
              "serialization_version": shared.SERIALIZATION_VERSION, "serializer_sha256": shared.STATE_SERIALIZER_SHA,
              "PRO_inputs_used": False, "counts": dict(counts), "next_skill_rows": len(train),
              "auxiliary_rows": sum(d["rows"] for d in files if d["bucket"] == "auxiliary"),
              "actual_request_matches": len(train), "unique_decision_keys": len(train),
              "unique_request_hashes": len({shared.digest(row["request"]) for row in train}),
              "uniqueness_note": "Scene/stage/step keys identify recorded decisions; they do not establish unique physical snapshots.",
              "by_task": {name: dict(c) for name, c in by_task.items()}, "files": files,
              "runtime_requests": {"path": str(runtime_path), "sha256": sha(runtime_path), "rows": len(runtime)},
              "token_p95": float(np.percentile(tokens, 95)) if tokens else None, "token_max": max(tokens) if tokens else None,
              "training_init_indices": sorted({r["init_state_index"] for r in train}), "excluded_init_overlap": 0,
              "validation_files": [], "remaining": "Independent development validation batch and Codex1 strict admission required; old raw prefixes unchanged."}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("files", "by_task")}))


if __name__ == "__main__":
    main()
