"""Replay one explicit captured request with vLLM generated-token tracing.

This is a new stochastic diagnostic attempt, not a replacement episode or
evidence of the original attempt's unrecorded pre-parser generation.
"""

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from tokenizers import Tokenizer


parser = argparse.ArgumentParser()
parser.add_argument("--requests", type=Path, required=True)
parser.add_argument("--index", type=int, default=0)
parser.add_argument("--backend", required=True)
parser.add_argument("--tokenizer", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
row = json.loads(args.requests.read_text().splitlines()[args.index])
body = row["request"]
original_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
assert original_sha == row["request_sha256"]
assert not body.get("stream")
body = {**body, "return_token_ids": True}
args.output.mkdir(parents=True, exist_ok=False)
(args.output / "request.json").write_text(json.dumps(body, indent=2))
start = time.monotonic()
request = urllib.request.Request(args.backend.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=600) as response:
    reply = json.load(response)
(args.output / "response.json").write_text(json.dumps(reply, indent=2))
tokenizer = Tokenizer.from_file(str(args.tokenizer))
records = []
for choice in reply["choices"]:
    ids = choice.get("token_ids")
    assert ids is not None, "backend did not return generated token IDs"
    records.append({"index": choice["index"], "generated_token_ids": ids, "raw_generated_text": tokenizer.decode(ids, skip_special_tokens=False), "parsed_message": choice["message"], "finish_reason": choice["finish_reason"]})
summary = {"purpose": "new_stochastic_request_replay_not_benchmark_or_original_generation", "source": str(args.requests), "source_row": args.index, "original_request_sha256": original_sha, "request_diff_keys": ["return_token_ids"], "backend": args.backend, "wall_s": time.monotonic() - start, "usage": reply.get("usage"), "tokenizer_sha256": hashlib.sha256(args.tokenizer.read_bytes()).hexdigest(), "records": records}
(args.output / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k != "records"}, indent=2))
