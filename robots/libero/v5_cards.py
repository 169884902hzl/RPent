# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Category-only cards; coordinates and simulator symbols are never steps."""

from robots.libero.v5_state import Candidate

VERSION = "category-card/1"
SKILLS = {"grasp", "place", "articulate", "retreat", "release", "finish"}


def validate_card(card: dict) -> None:
    """Validate the declared fields instead of accepting arbitrary recipe code."""
    if card.get("version") != VERSION or card.get("origin") not in ("original_oracle", "rpent_eval"):
        raise ValueError("unsupported card provenance/version")
    if not card.get("steps"):
        raise ValueError("empty card")
    for step in card["steps"]:
        if set(step) - {"skill", "object_category", "target_category", "mode"}:
            raise ValueError("card step must contain category selectors only")
        if step.get("skill") not in SKILLS:
            raise ValueError("unsupported card skill")
        for key in ("object_category", "target_category"):
            value = step.get(key)
            if value is not None and (not isinstance(value, str) or any(x in value for x in ("obj_", "zone_", "_region", "_site"))):
                raise ValueError("card contains a private identifier")


def card_view(card: dict | None, index: int) -> dict | None:
    """Produce the same public card line for oracle and evaluation cards."""
    if card is None or index >= len(card["steps"]):
        return None
    step = card["steps"][index]
    words = [step["skill"], step.get("object_category"), step.get("target_category"), step.get("mode")]
    return {"step": index + 1, "total": len(card["steps"]),
            "next": " ".join(word for word in words if word), "selector": step}


def resolve_card(view: dict, entities, held: str | None) -> Candidate | None:
    """Resolve category selectors from measured entities, rejecting ambiguity."""
    step = view["selector"]
    tool = step["skill"]
    if tool in ("retreat", "release", "finish"):
        return Candidate(tool)
    def bind(kind, *, source=False):
        options = [e for e in entities if e.visible and e.name == kind]
        if source and held:
            options = [e for e in options if e.id == held]
        return options[0].id if len(options) == 1 else None
    obj = bind(step.get("object_category"), source=tool == "place")
    if obj is None:
        return None
    target = bind(step.get("target_category")) if tool == "place" else None
    if tool == "place" and (target is None or held != obj):
        return None
    return Candidate(tool, obj, target, step.get("mode", "direct" if tool == "grasp" else None))


def advance_card(view, selected, receipt, resolved) -> bool:
    """Advance only after the matching measured skill has a verified receipt."""
    if view is None or resolved is None:
        return False
    same = selected == resolved or selected.tool == "card_next"
    return same and (receipt.get("verification") == "verified"
                     or resolved.tool in ("retreat", "release") and receipt.get("executed")
                     or resolved.tool == "finish" and receipt.get("executed"))


def from_successful_trace(records, *, identity, source_sha256) -> dict:
    """Convert a successful original expert trajectory to category-only steps."""
    steps = []
    for row in records:
        action = Candidate.from_text(row["selected"])
        if action.tool not in SKILLS or action.tool == "finish":
            continue
        if row["receipt"].get("error"):
            continue
        entities = {e["id"]: e for e in row["measurements"]}
        step = {"skill": action.tool}
        for field in ("object", "target"):
            value = getattr(action, field)
            if value:
                step[field + "_category"] = entities[value]["name"]
        if action.mode:
            step["mode"] = action.mode
        if not steps or steps[-1] != step:
            steps.append(step)
    steps.append({"skill": "finish"})
    card = {"version": VERSION, "origin": "original_oracle", "steps": steps,
            "source_episode": identity, "source_choices_sha256": source_sha256}
    validate_card(card)
    return card
