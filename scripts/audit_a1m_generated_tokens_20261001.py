"""Decode original vLLM generation records without replaying model requests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from tokenizers import Tokenizer


def main() -> None:
    """Compare generated function markup with the serving parser's output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    rows = []
    digest = hashlib.sha256()
    incomplete_lines = 0
    with args.responses.open("rb") as source:
        for index, line in enumerate(source):
            digest.update(line)
            try:
                record = json.loads(line)
            except ValueError:
                incomplete_lines += 1
                continue
            request = record.get("request", {})
            messages = request.get("messages", [])
            system = "\n".join(
                str(message.get("content", ""))
                for message in messages
                if message.get("role") == "system"
            )
            tags = sorted(set(re.findall(r"/episodes/(libero_\w+_t\d+_s\d+)", system)))
            for choice in record.get("response", {}).get("choices", []):
                token_ids = choice.get("token_ids")
                raw = (
                    tokenizer.decode(token_ids, skip_special_tokens=False)
                    if token_ids is not None
                    else None
                )
                tools = choice.get("message", {}).get("tool_calls") or []
                names = [call["function"]["name"] for call in tools]
                raw_names = re.findall(r"<function=([^>\s]+)>", raw or "")
                if raw is None:
                    boundary = "original_tokens_unavailable"
                elif names:
                    boundary = "structured_tools_returned"
                elif raw_names:
                    boundary = "generated_function_markup_without_structured_tools"
                elif "tool_call" in raw or "tool_response" in raw:
                    boundary = "generated_markup_without_function"
                else:
                    boundary = "generated_text_without_function"
                rows.append({
                    "line_index": index,
                    "episode_tags": tags,
                    "request_sha256": record["request_sha256"],
                    "status_code": record["status_code"],
                    "message_roles": [message.get("role") for message in messages],
                    "tool_receipts": sum(message.get("role") == "tool" for message in messages),
                    "image_items": sum(
                        item.get("type") == "image_url"
                        for message in messages
                        if isinstance(message.get("content"), list)
                        for item in message["content"]
                        if isinstance(item, dict)
                    ),
                    "usage": record.get("response", {}).get("usage"),
                    "finish_reason": choice.get("finish_reason"),
                    "generated_token_count": len(token_ids) if token_ids is not None else None,
                    "decoded_generation": raw,
                    "api_content": choice.get("message", {}).get("content"),
                    "api_tool_names": names,
                    "generated_function_names": raw_names,
                    "boundary": boundary,
                })
    result = {
        "purpose": "original_generated_tokens_development_diagnostic_not_Table_A",
        "response_prefix_sha256": digest.hexdigest(),
        "tokenizer_sha256": hashlib.sha256(args.tokenizer.read_bytes()).hexdigest(),
        "incomplete_lines": incomplete_lines,
        "choice_count": len(rows),
        "boundary_counts": dict(Counter(row["boundary"] for row in rows)),
        "limit": "Function markup alone does not prove valid arguments or a parser defect. Live ledgers are prefixes; no model request was replayed.",
        "choices": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({key: value for key, value in result.items() if key != "choices"}))


if __name__ == "__main__":
    main()
