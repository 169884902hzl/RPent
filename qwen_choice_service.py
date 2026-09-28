"""Serve the frozen Qwen3.5-4B Choice readout for the RPent planner."""

from __future__ import annotations

import argparse
import json
import math
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("qwen4b", "dagger2323"), required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18573)
    args = parser.parse_args()

    import torch
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration

    sys.path.insert(0, str(args.package))
    import parallel_schema

    tokenizer = AutoTokenizer.from_pretrained(args.package, local_files_only=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        args.base, dtype=torch.bfloat16, attn_implementation="sdpa",
        local_files_only=True,
    )
    if args.model == "dagger2323":
        weights = torch.load(args.checkpoint / "pytorch_model.bin", map_location="cpu",
                             mmap=True, weights_only=True)
        model.load_state_dict(weights, strict=True)
        del weights
    model = model.to("cuda").eval()
    model.config.use_cache = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ready", "model": args.model})
            else:
                self.send_error(404)

        def _send(self, status: int, value: dict) -> None:
            data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/score":
                self.send_error(404)
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                options = body["options"]
                if not 1 <= len(options) <= 26:
                    raise ValueError("Choice requires 1..26 options")
                codes = [f"C{i}" for i in range(len(options))]
                definition = {"action": {
                    "type": "enum", "description": body["instruction"],
                    "choices": codes,
                    "choice_descriptions": dict(zip(codes, options)),
                }}
                prepared = parallel_schema.prepare_prompts(
                    tokenizer, body["context"], definition, 2048,
                )
                ids = torch.tensor([prepared.full_ids[0]], device="cuda")
                with torch.inference_mode():
                    logits = model(input_ids=ids, use_cache=False,
                                   logits_to_keep=1).logits[0, -1]
                    probabilities = logits[prepared.candidate_ids[0]].float().softmax(-1).cpu().tolist()
                if not all(math.isfinite(p) for p in probabilities):
                    raise ValueError("nonfinite Choice probability")
                self._send(200, {
                    "model": args.model,
                    "selected": max(range(len(probabilities)), key=probabilities.__getitem__),
                    "probabilities": dict(zip(codes, probabilities)),
                    "prompt_tokens": len(prepared.full_ids[0]),
                })
            except Exception as exc:
                print(f"Choice request failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                self._send(422, {"error": f"{type(exc).__name__}: {exc}"})

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
