"""Validate selections against the exact public request; track repeat failures."""

from __future__ import annotations

import json
from concurrent.futures import Future
from pathlib import Path

from jsonschema import Draft202012Validator

from . import VERSION as VERSION

SCHEMA_PATH = Path(__file__).with_name("schema.json")
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
BOUNDARIES = {"observe", "call_vla", "finish", "ask_help"}


def is_boundary(candidate: dict) -> bool:
    """Only actions that hand off control statically terminate a chunk."""
    return candidate['skill'] in BOUNDARIES


def validate(value: dict) -> None:
    kind = value.get("kind")
    if kind not in {"request", "decision", "receipt", "prefix_context", "oracle_labels"}:
        raise ValueError("unknown bounded-skills message kind")
    schema = {key: val for key, val in SCHEMA.items() if key != "oneOf"}
    schema["$ref"] = f"#/$defs/{kind}"
    Draft202012Validator(schema).validate(value)
    if kind == "request":
        anchors = {anchor["id"] for anchor in value["anchors"]}
        if len(anchors) != len(value["anchors"]):
            raise ValueError("duplicate measured anchor ID")
        for relation in value.get("relations", []):
            if relation["source_id"] not in anchors or relation["target_id"] not in anchors:
                raise ValueError("relation references an unmeasured anchor")
        for candidate in value["candidates"]:
            for key in ("anchor_id", "target_id"):
                anchor = candidate["parameters"].get(key)
                if anchor is not None and anchor not in anchors:
                    raise ValueError("candidate references an unmeasured anchor")


def selected(request: dict, decision: dict) -> list[dict]:
    """Reject stale/invented actions and crossing a control-handoff boundary."""
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
    if any(is_boundary(c) for c in result[:-1]):
        raise ValueError("decision crosses a control-handoff boundary")
    return result


def validate_labels(request: dict, labels: dict) -> None:
    """Bind private set labels to one exact request and ordered prefix."""
    import hashlib

    validate(labels)
    digest = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    if (labels['request_sha256'] != digest or labels['observation_id'] != request['observation_id']
            or labels['revision'] != request['revision']):
        raise ValueError('oracle labels are for a different public request')
    ids = {c['id'] for c in request['candidates']}
    prefix = []
    for position in labels['positions']:
        if position['prefix'] != prefix:
            raise ValueError('oracle labels do not follow the selected prefix')
        legal = set(position['legal'])
        if not legal <= ids or position['selected'] not in legal:
            raise ValueError('oracle labels reference an illegal candidate')
        for field in ('rule_acceptable', 'measured_success', 'measured_failure'):
            if not set(position[field]) <= legal:
                raise ValueError('oracle label is outside its public legal set')
        if set(position['measured_success']) & set(position['measured_failure']):
            raise ValueError('conflicting measured success and failure')
        acceptable = (set(position['rule_acceptable']) | set(position['measured_success'])) - set(position['measured_failure'])
        if not acceptable or position['selected'] not in acceptable:
            raise ValueError('selected oracle action is outside the acceptable set')
        prefix.append(position['selected'])


def identity(candidate: dict) -> str:
    return json.dumps([candidate["skill"], candidate["parameters"]], sort_keys=True)


class FailureMemory:
    """Two no-effect/fail repeats block until a public scene change."""

    def __init__(self):
        self.counts: dict[str, int] = {}
        self.last: dict[str, str] = {}
        self.cooldown: dict[str, int] = {}

    def tick(self, *, scene_changed: bool, changed_anchors: set[str] | None = None) -> None:
        if scene_changed:
            if changed_anchors is None:
                self.counts.clear()
            else:
                # No-effect contact needs evidence that its own source changed.
                # An unrelated, partially occluded table centre is not progress
                # for that object. Collision failures still reset for any scene
                # change because a moved obstacle can make their route usable.
                self.counts = {key: n for key, n in self.counts.items()
                    if self.last.get(key) in {'contact_no_measured_progress', 'contact_motion_unmeasured',
                                             'contact_surface_motion_ambiguous'}
                    and (anchor := json.loads(key)[1].get('anchor_id')) is not None
                    and anchor not in changed_anchors}
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
