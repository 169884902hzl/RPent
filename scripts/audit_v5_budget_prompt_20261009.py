"""Count a frozen set of long recorded requests with the budget-format addition."""

import argparse
import hashlib
import heapq
import json
from pathlib import Path
import sys

from transformers import AutoTokenizer

from robots.libero.v5_skill_budget import action_costs
from robots.libero.v5_skill_budget import task_completion_receipt
from robots.libero.v5_state import Candidate, CHOICE_INSTRUCTION, receipt_lines, expand_receipt_metadata


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-receipt-fields", action="store_true",
                        help="Use maximum-width counter placeholders for token counting, never labels")
    args = parser.parse_args()
    sys.path.insert(0, str(args.package))
    import parallel_schema

    tokenizer = AutoTokenizer.from_pretrained(args.package, local_files_only=True)
    args.output.mkdir(parents=True, exist_ok=False)
    heap, counter = [], 0
    first = []
    for raw in args.episodes.read_text().splitlines():
        row = json.loads(raw)
        root = Path(row["output_dir"])
        paths = [root / "choices.jsonl", root / "rejected_request.json"]
        for path in paths:
            if not path.is_file():
                continue
            with path.open() as stream:
                records = ([json.loads(stream.read())] if path.suffix == ".json"
                           else (json.loads(line) for line in stream if line.strip()))
                for record in records:
                    request = record.get("request", record)
                    options = request.get("options", record.get("candidates"))
                    if not options:
                        continue
                    item = {"path": str(path), "decision": record.get("decision"),
                            "context": request["context"], "options": options,
                            "budget_placeholder_for_token_count_only": True}
                    # Tokenize the full contract, including option descriptions.
                    keys = [f"C{i}" for i in range(len(options))]
                    definition = {"action": {"type": "enum", "description": CHOICE_INSTRUCTION,
                        "choices": keys, "choice_descriptions": dict(zip(keys, options))}}
                    count = len(parallel_schema.prepare_prompts(tokenizer, item["context"], definition, 32768).full_ids[0])
                    if record.get("decision") == 0 and len(first) < 20:
                        first.append((count, counter, item))
                    heapq.heappush(heap, (count, counter, item))
                    if len(heap) > 128:
                        heapq.heappop(heap)
                    counter += 1
    selected = sorted({i: (n, i, row) for n, i, row in [*first, *heap]}.values(), reverse=True)
    report = []
    for old_count, _, item in selected:
        lines = item["context"].splitlines()
        failures = {line.split()[1]: line.split()[2]
                    for line in lines if line.startswith("candidate ")
                    and len(line.split()) == 3 and line.split()[2].startswith("failures=")}
        instruction = json.loads(next(line[12:] for line in lines if line.startswith("instruction ")))
        receipts = expand_receipt_metadata([json.loads(line[8:]) for line in lines if line.startswith("receipt ")],
                                           instruction=instruction)
        if args.project_receipt_fields:
            for receipt in receipts:
                # Counter placeholders are deliberately five digits wide.
                # This projection is not a physical replay or a training row.
                receipt.update(sim_steps_used=10000, remaining_sim_steps=10000,
                               skill_budget_version='public-skill-budget/1')
                task_completion_receipt(receipt, native_terminated=False, native_truncated=False)
        compact_rows = iter(receipt_lines(receipts, instruction=instruction))
        lines = [next(compact_rows) if line.startswith("receipt ") else line for line in lines]
        lines = [line for line in lines if not line.startswith("candidate ")]
        lines.append("budget remaining_sim_steps=10000 max_sim_steps=10000 src=public_action_counter")
        choices = [Candidate.from_text(value) for value in item["options"]]
        costs = action_costs(choices, receipts, max_chunks=160)
        values = [costs[action.text()]['estimated_sim_steps'] for action in choices]
        lines.append("candidate cost_order=option_keys cost_src=configured_skill_caps estimated_sim_steps="
                     + json.dumps(values, separators=(',', ':')))
        lines.append("candidate failures=count:type default=0:none ids=option_keys cost_src=configured_skill_caps")
        for index, action in enumerate(choices):
            if action.text() in failures:
                lines.append(f"candidate C{index} {failures[action.text()]}")
        context = "\n".join(lines)
        keys = [f"C{i}" for i in range(len(choices))]
        definition = {"action": {"type": "enum", "description": CHOICE_INSTRUCTION,
            "choices": keys, "choice_descriptions": dict(zip(keys, item["options"]))}}
        count = len(parallel_schema.prepare_prompts(tokenizer, context, definition, 32768).full_ids[0])
        report.append({**item, "before_tokens": old_count, "after_tokens": count,
                       "after_context": context, "over3072": count > 3072,
                       "receipt_field_projection_for_tokens_only": args.project_receipt_fields,
                       "same_action_options": True, "physical_replay": False})
    requests = args.output / "requests.jsonl"
    requests.write_text("".join(json.dumps(row) + "\n" for row in report))
    manifest = {"generator": ref(Path(__file__)), "input": ref(args.episodes),
                "examined_requests": counter, "selected_requests": len(report),
                "over3072": sum(row['over3072'] for row in report),
                "max_tokens": max(row['after_tokens'] for row in report),
                "runtime_limit_unchanged": 3072, "physical_replay": False,
                "historical_receipts_not_relabeled": not args.project_receipt_fields,
                "receipt_field_projection_for_tokens_only": args.project_receipt_fields,
                "state_source": ref(Path(sys.modules['robots.libero.v5_state'].__file__)),
                "budget_source": ref(Path(sys.modules['robots.libero.v5_skill_budget'].__file__)),
                "output": ref(requests)}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
