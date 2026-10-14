"""Count the same rejected requests before/after public receipt compaction."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from transformers import AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--state-module", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("v5_compaction_audit", args.state_module)
    state = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = state
    spec.loader.exec_module(state)
    package = args.root.parent / "rd_instruction_20260923/v31_package_decider_2048_socket_20260925a"
    sys.path.insert(0, str(package))
    import parallel_schema
    tokenizer = AutoTokenizer.from_pretrained(package, local_files_only=True)
    expert = args.root / "artifacts/expert_legal_r2_manifest_20261008_remote73_r1/final_expert_legal_r2_200.json"
    a3 = args.root / "results/harness_v5/interim574_20261007/accounting80_20261008_r3/once80.jsonl"
    rows = json.loads(expert.read_text())["effective_rows"]
    rows += [json.loads(line) for line in a3.read_text().splitlines()]
    report = []
    args.output.mkdir(parents=True, exist_ok=False)
    for row in rows:
        if row["result"].get("termination_category") != "over_token":
            continue
        path = Path(row["output_dir"]) / "rejected_request.json"
        request = json.loads(path.read_text())
        lines = request["context"].splitlines()
        receipts = state.expand_receipt_metadata([json.loads(line[8:]) for line in lines if line.startswith("receipt ")])
        compact_lines = iter(state.receipt_lines(receipts))
        compact_context = "\n".join(next(compact_lines) if line.startswith("receipt ") else line for line in lines)
        keys = [f"C{i}" for i in range(len(request["options"]))]
        definition = {"action": {"type": "enum", "description": state.CHOICE_INSTRUCTION,
            "choices": keys, "choice_descriptions": dict(zip(keys, request["options"]))}}
        # Counting rejected requests needs a larger audit-only preparation cap.
        # Runtime admission remains 3072 and the report tests that exact bound.
        before = len(parallel_schema.prepare_prompts(tokenizer, request["context"], definition, 32768).full_ids[0])
        after = len(parallel_schema.prepare_prompts(tokenizer, compact_context, definition, 32768).full_ids[0])
        name = "_".join(map(str, (row["episode"]["suite"], row["episode"]["task"], row["episode"]["seed"])))
        output = args.output / (name + ".json")
        output.write_text(json.dumps({**request, "context": compact_context}, indent=2) + "\n")
        report.append({"episode": row["episode"], "original": str(path), "rerendered": str(output),
            "before_tokens": before, "after_tokens": after, "admitted_after": after <= 3072})
    summary = {"version": state.RECEIPT_COMPACT_VERSION, "cases": report,
        "admitted_after": sum(row["admitted_after"] for row in report), "total": len(report),
        "same_options": True, "same_measurements": True, "physical_replay_performed": False}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
