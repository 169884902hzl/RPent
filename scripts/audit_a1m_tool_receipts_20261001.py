"""Recover executed tool receipts from actual API history after wall timeouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def summarize(messages: list[dict]) -> dict:
    names = {}
    counts = Counter()
    skills = []
    errors = []
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                names[call["id"]] = call["function"]["name"]
        if message.get("role") != "tool":
            continue
        name = message.get("name") or names.get(message.get("tool_call_id"), "unknown")
        counts[name] += 1
        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        try:
            data = json.loads(content) if isinstance(content, str) else content
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            continue
        if data.get("error"):
            errors.append({"tool": name, "error": str(data["error"])[:1500]})
        if name in ("pi0_pick", "pi0_doubled", "vla_act"):
            skills.append({"tool": name, "step": data.get("step"),
                           "terminated": data.get("terminated"),
                           "result": data.get("log", {}).get("result", {})})
    return {"executed_tool_receipt_counts": dict(counts),
            "executed_skill_receipts": skills, "structured_tool_errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256()
    episodes = {}
    incomplete = 0
    with args.responses.open("rb") as source:
        for line in source:
            digest.update(line)
            try:
                record = json.loads(line)
            except ValueError:
                incomplete += 1
                continue
            messages = record.get("request", {}).get("messages", [])
            system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
            for tag in set(re.findall(r"/episodes/(libero_\w+_t\d+_s\d+)", system)):
                episodes[tag] = {"request_sha256": record["request_sha256"],
                                 "unix_s": record["unix_s"], **summarize(messages)}
    result = {"purpose": "actual_executed_receipt_diagnostic_not_training_or_new_scores",
              "response_log_sha256": digest.hexdigest(), "incomplete_lines": incomplete,
              "limit": "Latest captured request history proves prior tool execution; the final generated calls may not yet have executed. Counts are not mutually exclusive causal classifications.",
              "episodes": episodes}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "episodes"}))
    for tag, row in sorted(episodes.items()):
        print(json.dumps({"episode": tag, "receipt_counts": row["executed_tool_receipt_counts"],
                          "skill_receipts": len(row["executed_skill_receipts"]),
                          "reported_skill_failures": sum(s["result"].get("success") is False for s in row["executed_skill_receipts"])}))


if __name__ == "__main__":
    main()
