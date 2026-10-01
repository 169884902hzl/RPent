"""Two-turn serving health diagnostic; no robot actions or benchmark scores."""

import argparse
import json
import time
import urllib.request
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--backend", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
tools = [
    {"type": "function", "function": {"name": "get_observation", "description": "Read the latest camera observation.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "finish", "description": "Report completion after verification.", "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["success", "failure"]}}, "required": ["status"], "additionalProperties": False}}},
]
messages = [
    {"role": "system", "content": "This is a synthetic tool-protocol check, not a robot task. First call get_observation. When its tool result says verified_complete=true, call finish with status success. Do not substitute prose for these calls."},
    {"role": "user", "content": "Run the two-step protocol check."},
]
records = []
for turn in range(2):
    body = {
        "model": "Qwen3.6-27B-FP8", "messages": messages, "tools": tools,
        "tool_choice": "auto", "max_completion_tokens": 8192,
        "temperature": 0.7, "top_p": 0.8, "top_k": 20,
        "min_p": 0.0, "presence_penalty": 1.5, "repetition_penalty": 1.0,
        "chat_template_kwargs": {"enable_thinking": False},
        "logit_bias": {"248068": -100, "248069": -100},
    }
    (args.output / f"request{turn}.json").write_text(json.dumps(body, indent=2))
    start = time.monotonic()
    request = urllib.request.Request(args.backend.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        reply = json.load(response)
    (args.output / f"response{turn}.json").write_text(json.dumps(reply, indent=2))
    message = reply["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    expected = "get_observation" if turn == 0 else "finish"
    ok = len(calls) == 1 and calls[0]["function"]["name"] == expected
    if turn == 1 and ok:
        ok = json.loads(calls[0]["function"]["arguments"]) == {"status": "success"}
    records.append({"turn": turn, "expected": expected, "structured_call_matches": ok, "wall_s": time.monotonic() - start, "usage": reply.get("usage"), "message": message})
    if not ok or turn == 1:
        break
    messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
    messages.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": '{"verified_complete":true}'})
summary = {"purpose": "synthetic_serving_tool_protocol_not_benchmark", "backend": args.backend, "all_two_turns_match": len(records) == 2 and all(r["structured_call_matches"] for r in records), "records": records}
(args.output / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
