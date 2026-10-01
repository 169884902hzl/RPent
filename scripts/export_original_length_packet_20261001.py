"""Export original development requests for memory checks, without labels."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--array-job", required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--shared-schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("LIBERO_TYPE") != "standard":
        raise ValueError("use original LIBERO development inputs only")
    from libero.libero import benchmark

    sys.path.insert(0, str(args.package))
    import parallel_schema

    spec = importlib.util.spec_from_file_location("length_shared_schema", args.shared_schema)
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    tokenizer = AutoTokenizer.from_pretrained(args.package, local_files_only=True)
    suites, initial_states, sources, requests, ledgers, seen = {}, {}, [], [], {}, set()
    for shard in (0, 1):
        path = args.results_root / f"job{args.array_job}_task{shard}" / "episodes.jsonl"
        data = path.read_bytes()
        if data and not data.endswith(b"\n"):
            data = data[: data.rfind(b"\n") + 1]
        ledgers[shard] = data
        sources.append({"path": str(path), "prefix_sha256": hashlib.sha256(data).hexdigest(), "prefix_bytes": len(data)})
        for line in data.splitlines():
            episode = json.loads(line)
            e = episode["episode"]
            key = (e["suite"], e["task"], e["seed"])
            if key[0] not in {"libero_spatial", "libero_object", "libero_goal", "libero_10"} or not 0 <= key[1] < 10 or not 0 <= key[2] < 5 or key in seen:
                raise ValueError("unexpected original development scene")
            seen.add(key)
            root = Path(episode["output_dir"])
            if root != path.parent / f"{key[0]}_t{key[1]}_s{key[2]}":
                raise ValueError("episode path differs from declared shard")
            trace = root / "choices.jsonl"
            if not trace.exists():
                continue
            trace_bytes = trace.read_bytes()
            source_hash = hashlib.sha256(trace_bytes).hexdigest()
            sources.append({"path": str(trace), "sha256": source_hash})
            if key[0] not in suites:
                suites[key[0]] = benchmark.get_benchmark_dict()[key[0]]()
            task_key = key[:2]
            if task_key not in initial_states:
                initial_states[task_key] = suites[key[0]].get_task_init_states(key[1])
            vector = np.asarray(initial_states[task_key][key[2]])
            initial_sha = hashlib.sha256(vector.tobytes(order="C")).hexdigest()
            for line_index, choice_line in enumerate(trace_bytes.splitlines()):
                choice = json.loads(choice_line)
                original = choice["request"]
                criteria = {f"C{i}": text for i, text in enumerate(original["options"])}
                wire = {"state": original["context"], "questions": {"action": {"type": "choice", "instructions": original["instruction"], "criteria": criteria}}}
                definition = {"action": {"type": "enum", "description": wire["questions"]["action"]["instructions"], "choices": list(criteria), "choice_descriptions": criteria}}
                prepared = parallel_schema.prepare_prompts(tokenizer, wire["state"], definition, 3072)
                count = len(prepared.full_ids[0])
                if count != choice["prompt_tokens"]:
                    raise ValueError(f"logged/shared token mismatch at {trace}:{line_index + 1}")
                if wire["state"].encode() != original["context"].encode() or list(criteria.values()) != original["options"]:
                    raise ValueError("state bytes or candidate order changed")
                requests.append({"purpose": "original_development_memory_only_never_training", "domain": "libero", "original_suite": key[0], "task_id": key[1], "init_state_index": key[2], "init_state_sha256": initial_sha, "init_state_dtype": str(vector.dtype), "init_state_shape": list(vector.shape), "step": choice["decision"], "request": wire, "request_sha256": shared.digest(wire), "prompt_tokens": count, "source": str(trace), "source_line": line_index + 1, "source_sha256": source_hash, "runtime_source_hashes": episode["result"].get("source_hashes", {})})
    args.output.mkdir(parents=True, exist_ok=False)
    for shard, data in ledgers.items():
        (args.output / f"ledger_prefix_task{shard}.jsonl").write_bytes(data)
    ranked = sorted(requests, key=lambda r: r["prompt_tokens"], reverse=True)
    files = {}
    for name, selected in (("longest128.jsonl", ranked[:128]), ("over2048.jsonl", [r for r in ranked if r["prompt_tokens"] > 2048])):
        data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected).encode()
        target = args.output / name
        target.write_bytes(data)
        files[name] = {"path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "rows": len(selected)}
    counts = sorted(r["prompt_tokens"] for r in ranked)
    manifest = {"purpose": "original_development_memory_only_never_training", "captured_at_unix_s": time.time(), "array_job": args.array_job, "completed_episode_prefix": len(seen), "rows": len(ranked), "p95": counts[int(.95 * (len(counts) - 1))] if counts else None, "max": max(counts) if counts else None, "over2048_rows": sum(x > 2048 for x in counts), "over3072_rows": sum(x > 3072 for x in counts), "token_recount_mismatches": 0, "state_or_candidate_order_changes": 0, "serialization_version": shared.SERIALIZATION_VERSION, "registered_state_serializer_sha": shared.STATE_SERIALIZER_SHA, "sources": sources, "files": files, "renderer_files": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in [args.shared_schema, args.package / "parallel_schema.py", Path(__file__)]}, "limit": "Immutable live prefix of completed original development episodes,not the final200 gate. No labels supplied,no training rows. Recorded requests are admitted under3072;uncaptured over3072 rejects are not included."}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sources"}, indent=2))


if __name__ == "__main__":
    main()
