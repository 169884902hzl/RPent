"""Loopback-only official Jev Choice bridge for the RPent comparison."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18574)
    args = parser.parse_args()
    sys.path.insert(0, "/home/agilex/cobot_magic/mojuco")
    from jev_harness.providers import TypeSafeClient

    client = TypeSafeClient()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def _send(self, status: int, body: dict) -> None:
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"status": "ready", "provider": "official_jev"})
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/score":
                self.send_error(404)
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                options = body["options"]
                if not 1 <= len(options) <= 26:
                    raise ValueError("Choice requires 1..26 options")
                keys = [f"C{i}" for i in range(len(options))]
                question = {"action": {
                    "type": "choice", "instructions": body["instruction"],
                    "criteria": dict(zip(keys, options)),
                }}
                reply = client.ask(body["context"], {}, question)
                self._send(200, {
                    "model": reply["provider"].get("actual_model"),
                    "selected": int(reply["selected"]["action"][1:]),
                    "probabilities": reply["raw"]["answers"]["action"]["probabilities"],
                })
            except Exception as exc:
                self._send(422, {"error": client.safe_error(exc)})

    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
