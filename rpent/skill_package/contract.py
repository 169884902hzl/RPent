"""Validate selections against the exact public request; track repeat failures."""

from __future__ import annotations

import json
from concurrent.futures import Future
from pathlib import Path

from jsonschema import Draft202012Validator

from . import VERSION

SCHEMA_PATH = Path(__file__).with_name("schema.json")
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))
BOUNDARIES = {"observe", "call_vla", "set_gripper", "release", "finish", "ask_help"}


def validate(value: dict) -> None:
    VALIDATOR.validate(value)


def selected(request: dict, decision: dict) -> list[dict]:
    """Reject stale/invented actions and crossing a contact boundary."""
    validate(request)
    validate(decision)
    if decision["observation_id"] != request["observation_id"] or decision["revision"] != request["revision"]:
        raise ValueError("decision is for a stale observation")
    ids = decision["candidate_ids"]
    if len(ids) > request["max_actions"]:
        raise ValueError("decision exceeds requested K")
    candidates = {c["id"]: c for c in request["candidates"]}
    if len(candidates) != len(request["candidates"]) or any(i not in candidates for i in ids):
        raise ValueError("unknown or duplicate candidate ID")
    result = [candidates[i] for i in ids]
    if any(c["skill"] in BOUNDARIES for c in result[:-1]):
        raise ValueError("decision crosses an observation/contact boundary")
    return result


def identity(candidate: dict) -> str:
    return json.dumps([candidate["skill"], candidate["parameters"]], sort_keys=True)


class FailureMemory:
    """Two no-effect/fail repeats block until a public scene change."""

    def __init__(self):
        self.counts: dict[str, int] = {}
        self.last: dict[str, str] = {}
        self.cooldown: dict[str, int] = {}

    def tick(self, *, scene_changed: bool) -> None:
        if scene_changed:
            self.counts.clear()
        self.cooldown = {key: n-1 for key, n in self.cooldown.items() if n > 1}

    def record(self, candidate: dict, outcome: str, reason: str) -> None:
        key = identity(candidate)
        if outcome in {"failure", "no_effect", "rejected", "unmeasured"}:
            self.counts[key] = self.counts.get(key, 0)+1
            self.last[key] = reason
        elif outcome == "success":
            self.counts.pop(key, None)
        if reason == "execution_error":
            self.cooldown[key] = 3

    def apply(self, candidates: list[dict]) -> list[dict]:
        return [{**c, "recent_failures": self.counts.get(identity(c), 0),
                 "last_failure": self.last.get(identity(c))} for c in candidates
                if self.counts.get(identity(c), 0) < 2 and not self.cooldown.get(identity(c), 0)]


class DecisionLookahead:
    """One async request, triggered by measured decision latency.

    The executor keeps following its screened chunk while this future runs.
    It must follow a screened braking tail if take() has no usable result.
    """

    def __init__(self, submit, decision_latency_s: float):
        if decision_latency_s < 0:
            raise ValueError("decision latency must be nonnegative")
        self.submit = submit
        self.latency = decision_latency_s
        self.pending: tuple[dict, Future] | None = None

    def poll(self, remaining_s: float, request_factory) -> None:
        if self.pending is None and remaining_s <= self.latency:
            request = request_factory()
            self.pending = request, self.submit(request)

    def take(self, observation_id: str, revision: int) -> list[dict] | None:
        if self.pending is None or not self.pending[1].done():
            return None
        request, future = self.pending
        self.pending = None
        if request["observation_id"] != observation_id or request["revision"] != revision:
            return None
        return selected(request, future.result())
