"""Audit receipt compression against completed, unchanged runtime requests."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def ref(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--state-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("receipt_suffix_audit", args.state_module)
    state = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = state
    spec.loader.exec_module(state)
    package = args.root.parent / "rd_instruction_20260923/v31_package_decider_2048_socket_20260925a"
    sys.path.insert(0, str(package))
    import parallel_schema
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(package, local_files_only=True)
    args.output.mkdir(parents=True, exist_ok=False)
    requests, inputs = [], [ref(args.episodes), ref(args.state_module), ref(Path(__file__))]
    for line in args.episodes.read_text().splitlines():
        episode = json.loads(line)
        choice_path = Path(episode["trace"]["choices"]["path"])
        if ref(choice_path) != episode["trace"]["choices"]:
            raise ValueError("completed choices changed")
        inputs.append(ref(choice_path))
        for line in choice_path.read_text().splitlines():
            event = json.loads(line)
            requests.append({"episode": episode["episode"], "decision": event["decision"],
                             "request": event["request"], "source": str(choice_path), "rejected": False})
        rejected = Path(episode["output_dir"]) / "rejected_request.json"
        if episode["result"]["termination_category"] == "over_token":
            inputs.append(ref(rejected))
            requests.append({"episode": episode["episode"], "decision": None,
                             "request": json.loads(rejected.read_text()), "source": str(rejected), "rejected": True})
    audited = []
    for item in requests:
        request = item["request"]
        lines = request["context"].splitlines()
        instruction = json.loads(next(line[12:] for line in lines if line.startswith("instruction ")))
        before_rows = [json.loads(line[8:]) for line in lines if line.startswith("receipt ")]
        expanded = state.expand_receipt_metadata(before_rows, instruction=instruction)
        encoded = state.receipt_lines(expanded, instruction=instruction)
        after_rows = [json.loads(line[8:]) for line in encoded]
        after_expanded = state.expand_receipt_metadata(after_rows, instruction=instruction)
        if canonical(expanded) != canonical(after_expanded):
            raise ValueError(f"receipt evidence changed: {item['source']}")
        replacements = iter(encoded)
        context = "\n".join(next(replacements) if line.startswith("receipt ") else line for line in lines)
        keys = [f"C{i}" for i in range(len(request["options"]))]
        definition = {"action": {"type": "enum", "description": state.CHOICE_INSTRUCTION,
                      "choices": keys, "choice_descriptions": dict(zip(keys, request["options"]))}}
        before = len(parallel_schema.prepare_prompts(tokenizer, request["context"], definition, 32768).full_ids[0])
        after = len(parallel_schema.prepare_prompts(tokenizer, context, definition, 32768).full_ids[0])
        audited.append({**item, "before_tokens": before, "after_tokens": after,
                        "receipt_expansion_byte_equal": True,
                        "rerendered_request": {**request, "context": context}})
    paths = []
    ordered = sorted(audited, key=lambda row: row["after_tokens"], reverse=True)
    groups = {"audit": [{k: v for k, v in row.items() if k not in ("request", "rerendered_request")}
                         for row in audited],
              "longest128": ordered[:128], "over2048": [row for row in ordered if row["after_tokens"] > 2048],
              "exact20": ordered[:20], "rejected_repaired": [row for row in audited if row["rejected"]]}
    for name, rows in groups.items():
        path = args.output / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        paths.append(ref(path))
    report = {"version": state.RECEIPT_COMPACT_VERSION, "requests": len(audited),
              "all_receipt_expansions_byte_equal": True, "same_options_and_other_state_lines": True,
              "before_max_tokens": max(row["before_tokens"] for row in audited),
              "after_max_tokens": max(row["after_tokens"] for row in audited),
              "before_over3072": sum(row["before_tokens"] > 3072 for row in audited),
              "after_over3072": sum(row["after_tokens"] > 3072 for row in audited),
              "after_over2048": len(groups["over2048"]),
              "rejected": [{k:v for k,v in row.items() if k not in ("request", "rerendered_request")}
                           for row in groups["rejected_repaired"]],
              "inputs": inputs, "outputs": paths, "physical_replay_performed": False,
              "new_training_rows": 0, "runtime_limit": 3072}
    path = args.output / "manifest.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({**{k:v for k,v in report.items() if k not in ("inputs", "outputs")}, "manifest": ref(path)}))


if __name__ == "__main__":
    main()
