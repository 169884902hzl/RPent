# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""System One action selection and optional completion diagnosis in one request."""

import json
import math
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def questions(instruction: str, options: list[str], *, goal_done: bool) -> dict:
    """Use the existing action prompt and measured-state completion evidence."""
    if not 1 <= len(options) <= 26:
        raise ValueError("System One choice requires 1..26 options")
    result = {"action": {"type": "choice", "instructions": instruction,
                         "criteria": {f"C{i}": text for i, text in enumerate(options)}}}
    if goal_done:
        result["goal_done"] = {
            "type": "noul",
            "instructions": "Have all requirements of the instruction been satisfied? Use measured observations and receipts; an executed action alone does not prove completion.",
            "criteria": {"true": "All instruction requirements are complete.",
                         "false": "The instruction is not yet complete."},
        }
    return result


def parse_answer(reply: dict, count: int, *, goal_done: bool, http_s: float) -> dict:
    """Preserve both server compute and HTTP latency without substituting one."""
    action = reply["answers"]["action"]
    choices = [f"C{i}" for i in range(count)]
    selected = choices.index(action["choice"])
    result = {"selected": selected, "probabilities": action["probabilities"],
              "model": reply["model"], "http_round_trip_s": http_s,
              "model_inference_s": None, "systemone_response": reply}
    compute_ms = reply.get("timing_ms", {}).get("compute")
    if compute_ms is not None:
        compute_ms = float(compute_ms)
        if not math.isfinite(compute_ms) or compute_ms < 0:
            raise ValueError("invalid System One compute time")
        result["model_inference_s"] = compute_ms / 1000.0
    if goal_done:
        probability = float(reply["answers"]["goal_done"]["noul"])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("invalid System One p(done)")
        result["goal_done_diagnostic"] = {"p_done": probability,
            "state_time": "before_action", "behavior_changed": False}
    return result


def score(endpoint: str, context: str, instruction: str, options: list[str], *,
          goal_done: bool = False, media: dict | None = None) -> dict:
    """Call a local model or official relay supporting the same System One API."""
    payload = {"state": context, "questions": questions(instruction, options, goal_done=goal_done)}
    if media is not None:
        payload["media"] = media
    endpoint = endpoint.rstrip("/")
    url = endpoint if endpoint.endswith("/v1/systemone") else endpoint + "/v1/systemone"
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=180) as response:
            reply = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"System One HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    result = parse_answer(reply, len(options), goal_done=goal_done,
                          http_s=time.perf_counter() - started)
    result["systemone_request"] = payload
    return result
