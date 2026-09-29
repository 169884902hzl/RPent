# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Pinned official-Jev evaluation relay; credentials stay in the local client."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MODEL = "jev-1.13.0"


def main() -> None:
    """Serve the measured-state choice contract on a distinct loopback port."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18582)
    parser.add_argument(
        "--client-source", type=Path, default=Path("/home/agilex/cobot_magic/mojuco")
    )
    args = parser.parse_args()
    sys.path.insert(0, str(args.client_source))
    from jev_harness.providers import TypeSafeClient

    client = TypeSafeClient()
    client.requested_model = MODEL
    health = client.health()
    if health["actual_model"] != MODEL:
        raise ValueError("official health probe returned a different model revision")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused) -> None:
            pass

        def send_json(self, status: int, payload: dict) -> None:
            encoded = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            if self.path == "/health":
                self.send_json(
                    200,
                    {
                        "status": "ready",
                        "model": MODEL,
                        "identity_verified": True,
                        "timing_kind": "http_round_trip",
                        "health_probe_http_s": health["probe_latency_s"],
                        "usage": "evaluation_only",
                    },
                )
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/score":
                self.send_error(404)
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                options = body["options"]
                if not 1 <= len(options) <= 24:
                    raise ValueError("v5 requires 1..24 choices")
                keys = [f"C{i}" for i in range(len(options))]
                question = {
                    "action": {
                        "type": "choice",
                        "instructions": body["instruction"],
                        "criteria": dict(zip(keys, options)),
                    }
                }
                reply = client.ask(body["context"], {}, question)
                if reply["provider"]["actual_model"] != MODEL:
                    raise ValueError(
                        "official response model differs from frozen revision"
                    )
                selected = keys.index(reply["selected"]["action"])
                self.send_json(
                    200,
                    {
                        "model": MODEL,
                        "selected": selected,
                        "probabilities": reply["raw"]["answers"]["action"][
                            "probabilities"
                        ],
                        "model_inference_s": None,
                        "http_round_trip_s": reply["latency_s"],
                        "envoy_upstream_s": None,
                        "decision_time_kind": "http_round_trip",
                        "raw": reply["raw"],
                        "selection_rule": reply["selection_rule"],
                    },
                )
            except Exception as error:
                self.send_json(422, {"error": client.safe_error(error)})

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
