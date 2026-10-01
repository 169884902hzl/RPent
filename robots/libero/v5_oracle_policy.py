# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Original-task script expert with bindings resolved from measured entities."""

from __future__ import annotations

import math
import re

from robots.libero.v5_runtime import category
from robots.libero.v5_state import Candidate, Entity, relations


def _kind(symbol: str) -> str:
    text = symbol.replace("_", " ")
    text = re.sub(r"^(?:the|an|a)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:left|right|front|back|top|bottom|upper|lower)\s+", "", text, flags=re.IGNORECASE)
    # Region suffixes identify private predicates, not extra object categories.
    text = re.sub(r"\s+\d+(?:\s+.*)?$", "", text)
    for word in ("cabinet", "drawer", "stove", "microwave", "ramekin", "rack"):
        if word in text:
            return word
    return category(text)


def goal_clause(instruction: str, symbol: str) -> str:
    """Bind each source to its own clause in a multi-object instruction."""
    kind = _kind(symbol)
    aliases = {
        "porcelain mug": ("porcelain mug", "white mug"),
        "white yellow mug": ("white yellow mug", "yellow and white mug", "white and yellow mug"),
        "barbecue sauce": ("barbecue sauce", "bbq sauce"),
        "black book": ("black book", "book"),
    }.get(kind, (kind,))
    clauses = re.split(r"\s+and\s+(?:put|place)\s+|\s+then\s+", instruction, flags=re.IGNORECASE)
    for clause in clauses:
        source = re.split(r"\b(?:on|in|into|to)\b", clause, maxsplit=1, flags=re.IGNORECASE)[0]
        if any(word in source.lower() for word in aliases):
            return clause
    return instruction


class OriginalOraclePolicy:
    """Use private goal predicates for progress, public measurements for motion."""

    def __init__(self, rpc) -> None:
        self.rpc = rpc
        self.last_binding: dict = {}
        self._bindings: dict[str, str] = {}
        self._complete = False

    @staticmethod
    def _caddy_compartment(
        entities: list[Entity], part: str, axes: tuple
    ) -> Entity | None:
        """Bind four measured caddy compartments in the public view frame."""
        compartments = [e for e in entities if e.name == "compartment"]
        if len(compartments) != 4:
            return None

        def projection(entity: Entity, axis: tuple) -> float:
            return sum(entity.xyz[i] * axis[i] for i in range(3))

        lateral = sorted(compartments, key=lambda e: projection(e, axes[0]))
        if (
            projection(lateral[1], axes[0]) - projection(lateral[0], axes[0]) <= 0.02
            or projection(lateral[3], axes[0]) - projection(lateral[2], axes[0]) <= 0.02
        ):
            return None
        if part == "left":
            return lateral[0]
        if part == "right":
            return lateral[3]
        central = sorted(lateral[1:3], key=lambda e: projection(e, axes[1]))
        if projection(central[1], axes[1]) - projection(central[0], axes[1]) <= 0.02:
            return None
        return central[0] if part == "back" else central[1]

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
        self, label: str, entities: list[Entity], phrase: str, axes: tuple, *, source_reference: bool = True
    ) -> Entity | None:
        """Reject unresolved references rather than binding by simulator IDs."""
        visible = [e for e in entities if e.visible]
        bound = self._bindings.get(label)
        if bound is not None:
            return next((e for e in visible if e.id == bound), None)
        kind = _kind(label)
        compartment = re.search(
            r"\b(front|back|left|right) compartment\b", phrase, flags=re.IGNORECASE
        )
        if "caddy" in kind and "region" in label and compartment:
            return self._caddy_compartment(visible, compartment[1].lower(), axes)
        drawer_part = re.search(
            r"\b(top|upper|middle|bottom|lower) drawer\b",
            (phrase or label.replace("_", " ")) if kind in ("cabinet", "drawer") else label.replace("_", " "),
            flags=re.IGNORECASE,
        )
        if drawer_part:
            kind = "drawer"
        if kind == "ramekin":
            return self._ramekin(visible)
        options = [e for e in visible if kind == e.name or kind in e.name]
        if kind == "bowl" and "black" in label:
            # An occluded black bowl can also have a small measured surface.
            # Use the subtype-size inference only when the public reference
            # actually names a ramekin; do not exclude arbitrary small bowls.
            ramekin = self._ramekin(visible) if "ramekin" in phrase else None
            if ramekin:
                options = [e for e in options if e.id != ramekin.id]
        if len(options) == 1:
            return options[0]
        if not options:
            return None
        if drawer_part:
            options.sort(key=lambda e: e.xyz[2])
            if any(b.xyz[2] - a.xyz[2] <= 0.02 for a, b in zip(options, options[1:])):
                return None
            part = drawer_part[1]
            if part in ("top", "upper"):
                return options[-1]
            if part in ("bottom", "lower"):
                return options[0]
            return options[len(options) // 2] if len(options) % 2 else None
        # The task language can contain both a source relation and a later
        # destination relation.  Restrict the anchor to the first action
        # clause so the source binding does not consume the trailing
        # ``and place ...`` clause.
        source_clause = re.split(
            r"\s+and\s+(?:place|put)\b|\s+then\s+",
            phrase,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        relation = re.search(
            r"\b(next to|on|in) (?:the )?(.+?)\s*$",
            source_clause,
            flags=re.IGNORECASE,
        ) if source_reference else None
        if relation:
            anchor = self.bind(relation[2], visible, "", axes)
            if anchor is None:
                return None
            options = [e for e in options if e.id != anchor.id]
            if relation[1] == "next to":
                ranked = sorted(
                    ((math.dist(e.xyz[:2], anchor.xyz[:2]), e) for e in options),
                    key=lambda pair: pair[0],
                )
                if ranked and (len(ranked) == 1 or ranked[1][0] - ranked[0][0] > 0.02):
                    return ranked[0][1]
                return None
            observed = set(relations([*options, anchor]))
            supported = [
                e
                for e in options
                if f"rel {e.id} {relation[1]} {anchor.id}" in observed
            ]
            # A measured contact can straddle a quantile edge, especially for
            # a bowl in a drawer or on a thin fixture.  Accept the same
            # relation when its measured XY lies in the anchor footprint and
            # its Z gap is within a measured-contact tolerance.
            if not supported and relation[1].lower() in ("on", "in"):
                predicate = relation[1].lower()
                supported = [
                    e
                    for e in options
                    if all(anchor.lower[i] - 0.02 <= e.xyz[i] <= anchor.upper[i] + 0.02 for i in (0, 1))
                    and (
                        abs(e.lower[2] - anchor.upper[2]) <= 0.06
                        if predicate == "on"
                        else e.upper[2] >= anchor.lower[2] - 0.04
                        and e.lower[2] <= anchor.upper[2] + 0.06
                    )
                ]
            return supported[0] if len(supported) == 1 else None
        if re.search(r"\btable cent(?:er|re)\b", phrase):
            table = self.bind("table", visible, "", axes)
            if table is None:
                # LIBERO's table is a support surface rather than a
                # segmentable task object.  Estimate its centre from the
                # measured support-level entities; this stays within the
                # public RGB-D geometry contract and remains ambiguous when
                # measurements do not separate a unique candidate.
                support = [
                    e for e in visible
                    if not any(word in e.name for word in ("cabinet", "drawer", "stove", "microwave"))
                ]
                if len(support) < 2:
                    return None
                z_values = sorted(e.lower[2] for e in support)
                mid = len(z_values) // 2
                z0 = z_values[mid] if len(z_values) % 2 else (z_values[mid - 1] + z_values[mid]) / 2
                support = [e for e in support if abs(e.lower[2] - z0) <= 0.05]
                if len(support) < 2:
                    return None
                # The support-object bounding box is a measured estimate of
                # the visible work surface centre.  A coordinate median is
                # biased toward a cluster of objects on one side of the
                # table (as in the bowl/plate scene).
                centre = tuple(
                    (min(e.xyz[i] for e in support) + max(e.xyz[i] for e in support)) / 2
                    for i in (0, 1)
                )
            else:
                centre = tuple((table.lower[i] + table.upper[i]) / 2 for i in (0, 1))
            ranked = sorted(
                ((math.dist(e.xyz[:2], centre), e) for e in options),
                key=lambda pair: pair[0],
            )
            if len(ranked) == 1 or ranked[1][0] - ranked[0][0] > 0.02:
                return ranked[0][1]
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
            if re.search(rf"\b{words}\b", phrase or label):
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
        pending_storage = {goal[2] for goal, complete in zip(status["goals"], status["satisfied"])
                           if not complete and goal[0] == "in" and len(goal) == 3}
        ordered = sorted(zip(status["goals"], status["satisfied"]),
                         key=lambda pair: pair[0][0] == "close" and pair[0][1] in pending_storage)
        for goal, satisfied in ordered:
            if satisfied:
                continue
            predicate, symbol = goal[:2]
            clause = goal_clause(instruction, symbol)
            source_phrase = re.split(r" and (?:place|put)| then |,", clause, maxsplit=1)[0]
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
                target = self.bind(goal[2], entities, clause, axes, source_reference=False)
                self.last_binding["target_entity"] = target.id if target else None
                if target is None:
                    break
                self._bindings[goal[2]] = target.id
                if status.get("storage_open", {}).get(goal[2]) is False:
                    return next(
                        (c for c in choices if c.tool == "articulate" and c.object == target.id and c.mode == "open"),
                        Candidate("ask_help"),
                    )
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
