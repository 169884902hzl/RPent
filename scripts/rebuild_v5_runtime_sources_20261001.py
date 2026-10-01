"""Rebuild independent request sources from explicitly declared runtime logs."""

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from robots.libero.v5_collection import wire_request
from shared_v5r_schema import digest, request_bytes


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.manifest = args.manifest.resolve()
    args.output = args.output.resolve()
    manifest = json.loads(args.manifest.read_text())
    evidence = json.loads(Path(manifest.get("input_manifest", args.manifest)).read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    paths = dict.fromkeys(Path(item["path"]).parent / "choices.jsonl" for item in evidence["files"])
    sources, source_map, declared, missing = [], {}, [], []
    methods = Counter()
    for path in paths:
        records = read_rows(path)
        declared.append({"path": str(path), "sha256": sha(path), "rows": len(records)})
        for index, record in enumerate(records):
            actual = wire_request(record["request"])
            source = {"request": actual, "source_file": str(path), "source_file_sha256": sha(path),
                      "source_line": index + 1, "stage": "skill", "step": record["decision"]}
            sources.append(source)
            source_map[digest(actual)] = source
            post = None
            if "post_request" in record:
                post = wire_request(record["post_request"])
                method = "explicit_post_request"
            elif index + 1 < len(records):
                # The pinned runner executes no perception or motion between
                # after_action and the next serialized request. Use that next
                # actual context, retaining this action's original question.
                assert records[index + 1]["decision"] == record["decision"] + 1
                post = copy.deepcopy(actual)
                post["state"] = records[index + 1]["request"]["context"]
                method = "next_actual_context_no_intervening_action"
            elif record["receipt"]["tool"] in ("finish", "ask_help"):
                # These tools only append their receipt in Executor.execute.
                # Entities, measured gripper and held state remain unchanged.
                lines = actual["state"].splitlines()
                receipts = [line for line in lines if line.startswith("receipt ")]
                receipts.append("receipt " + json.dumps(record["receipt"], sort_keys=True, separators=(",", ":")))
                post = copy.deepcopy(actual)
                post["state"] = "\n".join([line for line in lines if not line.startswith("receipt ")] + receipts[-3:])
                method = "terminal_no_motion_append_receipt"
            if post is None:
                missing.append({"source_file": str(path), "source_line": index + 1,
                                "reason": "last motion has no independent post-robot context"})
                continue
            methods[method] += 1
            source = {**source, "request": post, "stage": "receipt", "reconstruction": method}
            sources.append(source)
            source_map[digest(post)] = source
    ledger = args.output / "runtime_source_ledger.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sources))
    counts, selected, unsupported = Counter(), [], []
    for item in manifest["files"]:
        if item["bucket"] != "auxiliary":
            continue
        path = Path(item["path"])
        assert sha(path) == item["sha256"]
        for line_no, row in enumerate(read_rows(path), 1):
            source = source_map.get(row["base_request_sha256"])
            if source is None:
                unsupported.append({"source_file": str(path), "source_line": line_no,
                                    "question_type": row["question_type"], "reason": "independent_runtime_source_unavailable"})
                continue
            assert row["request"]["state"] == source["request"]["state"]
            selected.append(row)
            counts[row["question_type"]] += 1
    for item in manifest["files"]:
        if item["bucket"] == "train":
            assert sha(item["path"]) == item["sha256"]
            for row in read_rows(item["path"]):
                assert request_bytes(row["request"]) == request_bytes(source_map[digest(row["request"])]["request"])
    aux = args.output / "auxiliary.jsonl"
    aux.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected))
    exclusions = args.output / "unsupported_auxiliary_sources.json"
    exclusions.write_text(json.dumps({"rows": unsupported, "unrecoverable_post_states": missing}, indent=2) + "\n")
    descriptor = lambda p, n: {"path": str(p), "sha256": sha(p), "rows": n}
    report = {**manifest, "purpose": "corrected partial package with independently reconstructed runtime sources; not SFT admission",
              "upstream_manifest": str(args.manifest), "upstream_manifest_sha256": sha(args.manifest),
              "files": [d for d in manifest["files"] if d["bucket"] == "train"] + [{**descriptor(aux, len(selected)), "bucket": "auxiliary"}],
              "source_files": [descriptor(ledger, len(sources))], "runtime_logs": declared,
              "auxiliary_rows": len(selected), "auxiliary_by_question": dict(counts),
              "reconstruction_methods": dict(methods), "unsupported_auxiliary_rows": len(unsupported),
              "unsupported_auxiliary_evidence": descriptor(exclusions, len(unsupported)),
              "source_script_sha256": sha(__file__), "training_started": False, "is_independent_admission": False}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("next_skill_rows", "auxiliary_rows", "auxiliary_by_question", "reconstruction_methods", "unsupported_auxiliary_rows")}))


if __name__ == "__main__":
    main()
