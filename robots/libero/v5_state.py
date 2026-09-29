# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Measured entities, bounded choices and receipts for LIBERO harness v5."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any

VERSION = "libero-harness/5-dev"
CHOICE_INSTRUCTION = (
    "Choose the next action for the instruction from measured entities and "
    "receipts. Finish only when completion has evidence; ask_help if needed."
)
STAGING = ("direct", "above_10cm", "yaw_90")


@dataclass(frozen=True)
class Entity:
    """An instance measured from an RGB-D mask, in world metres."""

    id: str
    name: str
    xyz: tuple[float, float, float]
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]
    visible: bool = True
    source_step: int = 0

    def __post_init__(self) -> None:
        values = (*self.xyz, *self.lower, *self.upper)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("nonfinite perception measurement")
        if any(lo > hi for lo, hi in zip(self.lower, self.upper)):
            raise ValueError("invalid measured bounds")


@dataclass(frozen=True)
class Candidate:
    """A finite skill choice; numerical motion is resolved by the executor."""

    tool: str
    object: str | None = None
    target: str | None = None
    mode: str | None = None

    def text(self) -> str:
        args = [x for x in (self.object, self.target, self.mode) if x is not None]
        return f"{self.tool}({','.join(args)})"


def relations(
    entities: list[Entity],
    threshold: float = 0.02,
    right_axis: tuple = (1, 0, 0),
    front_axis: tuple = (0, -1, 0),
) -> list[str]:
    """Derive relations only from measured centres and surface bounds."""
    result = []
    for a in entities:
        for b in entities:
            if a.id == b.id or not (a.visible and b.visible):
                continue
            delta = [a.xyz[i] - b.xyz[i] for i in range(3)]
            if sum(delta[i] * right_axis[i] for i in range(3)) < -threshold:
                result.append(f"rel {a.id} left_of {b.id}")
            if sum(delta[i] * front_axis[i] for i in range(3)) > threshold:
                result.append(f"rel {a.id} in_front_of {b.id}")
            inside_xy = all(b.lower[i] <= a.xyz[i] <= b.upper[i] for i in (0, 1))
            if inside_xy and 0 <= a.lower[2] - b.upper[2] <= threshold:
                result.append(f"rel {a.id} on {b.id}")
            if inside_xy and b.lower[2] <= a.xyz[2] <= b.upper[2]:
                result.append(f"rel {a.id} in {b.id}")
            if math.dist(a.xyz, b.xyz) <= threshold:
                result.append(f"rel {a.id} near {b.id}")
    return result


def fixture_actions(name: str) -> tuple[str, ...]:
    if any(word in name for word in ("drawer", "cabinet", "microwave")):
        return ("open", "close")
    if any(word in name for word in ("stove", "switch", "faucet")):
        return ("turn_on", "turn_off")
    return ()


def candidates(
    entities: list[Entity],
    instruction: str,
    eef_xyz: tuple[float, ...],
    held: str | None,
    receipts: list[dict],
    rng: random.Random,
    card: dict | None = None,
) -> list[Candidate]:
    """Enumerate at most 24 skills from perception, with no goal access."""
    visible = [e for e in entities if e.visible]
    visible.sort(
        key=lambda e: (
            e.name.lower() not in instruction.lower(),
            math.dist(e.xyz, eef_xyz),
            e.id,
        )
    )
    selected = visible[:8]
    control = [
        Candidate(x) for x in ("reperceive", "retreat", "release", "finish", "ask_help")
    ]
    if card is not None:
        control.append(Candidate("card_next"))
    if receipts and receipts[-1].get("tool") in ("grasp", "regrasp_restage"):
        if receipts[-1].get("grasp_verified") is False:
            obj = receipts[-1].get("object")
            if any(e.id == obj and e.visible for e in entities):
                control.append(Candidate("regrasp_restage", obj))
    motions = []
    # Round-robin staging retains object coverage when there are >6 objects.
    if held is None:
        for mode in STAGING:
            for e in selected:
                actions = fixture_actions(e.name)
                if actions:
                    if mode == STAGING[0]:
                        motions.extend(
                            Candidate("articulate", e.id, mode=a) for a in actions
                        )
                else:
                    motions.append(Candidate("grasp", e.id, mode=mode))
    else:
        motions.extend(
            Candidate("place", held, e.id, mode)
            for e in selected
            if e.id != held
            for mode in ("on", "in")
        )
        motions.extend(
            Candidate("articulate", e.id, mode=a)
            for e in selected
            for a in fixture_actions(e.name)
        )
    result = motions[: 24 - len(control)] + control
    rng.shuffle(result)
    return result


def serialize(
    instruction: str,
    entities: list[Entity],
    gripper_opening: float,
    held: str | None,
    receipts: list[dict],
    card: dict | None = None,
    view_axes: tuple[tuple, tuple] | None = None,
) -> str:
    """Write planner state without simulator identifiers or goal predicates."""
    lines = [f"instruction {json.dumps(instruction, ensure_ascii=True)}"]
    for e in entities:
        xyz = [round(x * 100, 2) for x in e.xyz]
        size = [round((hi - lo) * 100, 2) for lo, hi in zip(e.lower, e.upper)]
        lines.append(
            f"e {e.id} name={json.dumps(e.name)} xyz_cm={xyz} size_cm={size} "
            f"visible={int(e.visible)} src=perception"
        )
    if view_axes is None:
        lines.extend(relations(entities))
    else:
        right, front = view_axes
        lines.append(
            f"rel frame=agentview_planar right_world={list(right)} "
            f"front_world={list(front)} threshold_cm=2"
        )
        lines.extend(relations(entities, right_axis=right, front_axis=front))
    lines.append(f"robot gripper_opening={gripper_opening:.4f} held={held or 'none'}")
    for receipt in receipts[-3:]:
        lines.append(
            "receipt " + json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        )
    if card is not None:
        lines.append(
            f"card step={card['step']}/{card['total']} next={json.dumps(card['next'])}"
        )
    return "\n".join(lines)


def prepare_request(
    tokenizer: Any, prepare_prompts: Any, context: str, choices: list[Candidate]
) -> tuple[dict, int]:
    """Admit the complete letter-readout prompt; never truncate state or choices."""
    if not 1 <= len(choices) <= 24:
        raise ValueError("v5 requires 1..24 choices")
    options = [c.text() for c in choices]
    keys = [f"C{i}" for i in range(len(options))]
    definition = {
        "action": {
            "type": "enum",
            "description": CHOICE_INSTRUCTION,
            "choices": keys,
            "choice_descriptions": dict(zip(keys, options)),
        }
    }
    prepared = prepare_prompts(tokenizer, context, definition, 2048)
    tokens = len(prepared.full_ids[0])
    if tokens > 2048:
        raise ValueError(f"complete request has {tokens} tokens > 2048")
    return {
        "context": context,
        "instruction": CHOICE_INSTRUCTION,
        "options": options,
    }, tokens


def grasp_verified(before: Entity, after: Entity | None, opening: float) -> bool:
    """Require gripper aperture and a measured 3 cm rise after the 5 cm trial."""
    return bool(
        after
        and after.visible
        and 0.005 <= opening <= 0.07
        and after.xyz[2] - before.xyz[2] >= 0.03
    )


def place_verified(
    first: Entity | None,
    second: Entity | None,
    target: Entity,
    opening: float,
    eef_xyz: tuple[float, ...],
    interval_s: float,
) -> bool:
    """Require two stable measurements, release and withdrawal."""
    if first is None or second is None or not (first.visible and second.visible):
        return False
    return bool(
        interval_s >= 0.3
        and opening >= 0.07
        and math.dist(first.xyz, second.xyz) <= 0.02
        and math.dist(eef_xyz, second.xyz) >= 0.05
        and all(
            target.lower[i] <= e.xyz[i] <= target.upper[i]
            for e in (first, second)
            for i in (0, 1)
        )
        and all(e.xyz[2] > target.upper[2] for e in (first, second))
    )


def entity_record(e: Entity) -> dict:
    """Expose measurement provenance for offline audits, separately from text."""
    return {**asdict(e), "src": "perception", "extent": "visible_surface"}
