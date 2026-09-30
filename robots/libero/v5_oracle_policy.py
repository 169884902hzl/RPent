# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Original-task script expert with bindings resolved from measured entities."""

from __future__ import annotations

import math
import re

from robots.libero.v5_runtime import category
from robots.libero.v5_state import Candidate, Entity


def _kind(symbol: str) -> str:
    text = symbol.replace("_", " ")
    # Region suffixes identify private predicates, not extra object categories.
    text = re.sub(r"\s+\d+(?:\s+.*)?$", "", text)
    for word in ("cabinet", "drawer", "stove", "microwave", "ramekin"):
        if word in text:
            return word
    return category(text)


class OriginalOraclePolicy:
    """Use private goal predicates for progress, public measurements for motion."""

    def __init__(self, rpc) -> None:
        self.rpc = rpc
        self.last_binding: dict = {}
        self._bindings: dict[str, str] = {}
        self._complete = False

    @staticmethod
    def _ramekin(entities: list[Entity]) -> Entity | None:
        exact = [e for e in entities if "ramekin" in e.name]
        if len(exact) == 1:
            return exact[0]
        # Ramekins are a small bowl subtype; use the public surface extents
        # only when one instance is clearly smaller than the others.
        bowls = [e for e in entities if e.name == "bowl"]

        def area(e: Entity) -> float:
            return (e.upper[0] - e.lower[0]) * (e.upper[1] - e.lower[1])

        bowls.sort(key=area)
        if len(bowls) >= 2 and area(bowls[0]) < 0.75 * area(bowls[1]):
            return bowls[0]
        return None

    def bind(
        self, label: str, entities: list[Entity], phrase: str, axes: tuple
    ) -> Entity | None:
        """Reject unresolved references rather than binding by simulator IDs."""
        visible = [e for e in entities if e.visible]
        bound = self._bindings.get(label)
        if bound is not None:
            return next((e for e in visible if e.id == bound), None)
        kind = _kind(label)
        if kind == "ramekin":
            return self._ramekin(visible)
        options = [e for e in visible if kind == e.name or kind in e.name]
        if kind == "bowl" and "black" in label:
            ramekin = self._ramekin(visible)
            if ramekin:
                options = [e for e in options if e.id != ramekin.id]
        if len(options) == 1:
            return options[0]
        if not options:
            return None
        between = re.search(r"between the (.+?) and the (.+?)(?:,|$)", phrase)
        if between:
            first = self.bind(between[1], visible, "", axes)
            second = self.bind(between[2], visible, "", axes)
            if first is None or second is None:
                return None
            delta = [second.xyz[i] - first.xyz[i] for i in (0, 1)]
            norm2 = sum(x * x for x in delta)
            if norm2 < 1e-6:
                return None
            ranked = []
            for e in options:
                fraction = (
                    sum((e.xyz[i] - first.xyz[i]) * delta[i] for i in (0, 1)) / norm2
                )
                if not 0 < fraction < 1:
                    continue
                projected = [first.xyz[i] + fraction * delta[i] for i in (0, 1)]
                ranked.append((math.dist(e.xyz[:2], projected), e))
            ranked.sort(key=lambda pair: pair[0])
            if ranked and (len(ranked) == 1 or ranked[1][0] - ranked[0][0] > 0.02):
                return ranked[0][1]
            return None
        right, front = axes
        for words, axis, sign in (
            ("left", right, -1),
            ("right", right, 1),
            ("front", front, 1),
            ("back", front, -1),
        ):
            if re.search(rf"\b{words}\b", phrase):
                options.sort(
                    key=lambda e: sign * sum(e.xyz[i] * axis[i] for i in range(3)),
                    reverse=True,
                )
                gap = abs(
                    sum(
                        (options[0].xyz[i] - options[1].xyz[i]) * axis[i]
                        for i in range(3)
                    )
                )
                return options[0] if gap > 0.02 else None
        return None

    def choose(
        self,
        entities: list[Entity],
        choices: list[Candidate],
        held: str | None,
        receipts: list[dict],
        instruction: str,
        axes: tuple,
        *,
        native_success: bool = False,
    ) -> Candidate:
        """Select one of the same visible finite choices, never synthesize motion."""
        status = self.rpc.call("oracle.status", timeout_s=120)
        self._complete |= bool(status["done"] or native_success)
        if self._complete:
            self.last_binding = {
                "completion_basis": "private_original_official_success"
            }
            return next(c for c in choices if c.tool == "finish")
        source_phrase = re.split(
            r" and (?:place|put)| then |,", instruction, maxsplit=1
        )[0]
        for goal, satisfied in zip(status["goals"], status["satisfied"]):
            if satisfied:
                continue
            predicate, symbol = goal[:2]
            obj = self.bind(symbol, entities, source_phrase, axes)
            self.last_binding = {
                "goal_kind": predicate,
                "source_entity": obj.id if obj else None,
                "basis": "measured_category_extent_and_instruction_relation",
            }
            if obj is None:
                break
            self._bindings[symbol] = obj.id
            if predicate in ("on", "in") and len(goal) == 3:
                target = self.bind(goal[2], entities, instruction, axes)
                self.last_binding["target_entity"] = target.id if target else None
                if target is None:
                    break
                self._bindings[goal[2]] = target.id
                if held is not None and held != obj.id:
                    return next(c for c in choices if c.tool == "release")
                if held is None:
                    attempted = sum(
                        r.get("object") == obj.id and r.get("grasp_verified") is False
                        for r in receipts
                    )
                    modes = ("direct", "above_10cm", "yaw_90")
                    allowed = [
                        c for c in choices if c.tool == "grasp" and c.object == obj.id
                    ]
                    preferred = modes[min(attempted, 2)]
                    return next(
                        (c for c in allowed if c.mode == preferred),
                        next((c for c in allowed), Candidate("ask_help")),
                    )
                return next(
                    (
                        c
                        for c in choices
                        if c.tool == "place"
                        and c.object == held
                        and c.target == target.id
                        and c.mode == predicate
                    ),
                    Candidate("ask_help"),
                )
            mode = {
                "open": "open",
                "close": "close",
                "turnon": "turn_on",
                "turnoff": "turn_off",
            }.get(predicate)
            if mode:
                return next(
                    (
                        c
                        for c in choices
                        if c.tool == "articulate"
                        and c.object == obj.id
                        and c.mode == mode
                    ),
                    Candidate("ask_help"),
                )
        return next(c for c in choices if c.tool == "ask_help")
