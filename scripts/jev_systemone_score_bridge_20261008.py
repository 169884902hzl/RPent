"""Expose the unchanged official /score relay through the choice System One API."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen


def upstream_json(endpoint, suffix, payload=None):
    request = Request(endpoint.rstrip("/") + suffix,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=180) as response:
        return json.load(response)


def relay_choice(endpoint, payload):
    if set(payload) != {"state", "questions"} or set(payload["questions"]) != {"action"}:
        raise ValueError("This relay bridge supports the unchanged action question only")
    action = payload["questions"]["action"]
    if action["type"] != "choice":
        raise ValueError("The official /score relay supports a choice question")
    criteria = action["criteria"]
    keys = [f"C{index}" for index in range(len(criteria))]
    if set(criteria) != set(keys):
        raise ValueError("Action criteria must retain the C0..Cn order")
    reply = upstream_json(endpoint, "/score", {"context": payload["state"],
        "instruction": action["instructions"], "options": [criteria[key] for key in keys]})
    if reply.get("model") != "jev-1.13.0":
        raise ValueError("Official Jev model identity changed")
    selected = int(reply["selected"])
    if not 0 <= selected < len(keys):
        raise ValueError("Official Jev returned an out-of-range choice")
    return {"model": reply["model"], "answers": {"action": {"type": "choice",
        "choice": keys[selected], "probabilities": reply["probabilities"]}},
        "relay_adapter": "systemone_to_unchanged_score/1",
        "relay_timing_kind": "http_round_trip; server compute unavailable",
        "upstream_reply": reply}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *values):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/health":
                return self.reply(404, {"error": "unknown path"})
            try:
                health = upstream_json(args.upstream, "/health")
                if health.get("model") != "jev-1.13.0" or health.get("identity_verified") is not True:
                    raise ValueError("Official relay identity not verified")
                self.reply(200, {**health, "relay_adapter": "systemone_to_unchanged_score/1",
                    "upstream_endpoint": args.upstream,
                    "prompt_and_options_transformed": False, "server_compute_available": False})
            except Exception as error:
                self.reply(502, {"error": f"{type(error).__name__}: {error}"})

        def do_POST(self):
            if self.path != "/v1/systemone":
                return self.reply(404, {"error": "unknown path"})
            try:
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.reply(200, relay_choice(args.upstream, payload))
            except Exception as error:
                self.reply(502, {"error": f"{type(error).__name__}: {error}"})

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
