# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Original-task script expert with bindings resolved from measured entities."""

from __future__ import annotations

import math
import re

from robots.libero.v5_runtime import category, instruction_regions, region_name
from robots.libero.v5_state import Candidate, Entity, relations


def _kind(symbol: str) -> str:
    # Digits can be part of the category (chefmate_8_frypan); remove only
    # the final instance suffix and a following named region suffix.
    symbol = re.sub(r"_\d+(?:_[a-z]+)*_(?:region|site)$", "", symbol)
    symbol = re.sub(r"_\d+$", "", symbol)
    text = symbol.replace("_", " ")
    text = re.sub(r"^(?:the|an|a)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:left|right|front|back|top|bottom|upper|lower)\s+", "", text, flags=re.IGNORECASE)
    # Region suffixes identify private predicates, not extra object categories.
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
    clauses = re.split(r"\s+(?:and|then)\s+(?:put|place)\s+(?!(?:it|them)\b)",
                       instruction, flags=re.IGNORECASE)
    for clause in clauses:
        source = re.split(r"\b(?:on|in|into|to)\b", clause, maxsplit=1, flags=re.IGNORECASE)[0]
        if any(word in source.lower() for word in aliases):
            if re.search(r"\binside\b", clause, re.IGNORECASE) and re.search(
                r"\b(?:drawer|cabinet)\b", instruction, re.IGNORECASE
            ) and not re.search(r"\b(?:drawer|cabinet)\b", clause, re.IGNORECASE):
                return instruction
            return clause
    return instruction


class OriginalOraclePolicy:
    """Use private goal predicates for progress, public measurements for motion."""

    def __init__(self, rpc) -> None:
        self.rpc = rpc
        self.last_binding: dict = {}
        self._bindings: dict[str, str] = {}
        self._binding_peers: dict[str, set[str]] = {}
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
        if not source_reference and label.endswith("_region"):
            named = [e for e in visible if e.name in {
                region_name(direction, anchor) for direction, anchor in instruction_regions(phrase)
            }]
            if len(named) == 1:
                return named[0]
        visible = [e for e in visible if not e.name.startswith("area ")]
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
        bound = self._bindings.get(label)
        if bound is not None:
            current = next(
                (e for e in visible if e.id == bound and (kind == e.name or kind in e.name)),
                None,
            )
            if current is not None:
                return current
            # Refresh can lose or recategorize a mask and later measure the
            # same named object under another public ID. Resolve its public
            # reference again; a stale ID must not hide a unique measurement.
        options = [e for e in visible if kind == e.name or kind in e.name]
        if bound is not None:
            # A previously distinct visible instance cannot become the lost
            # source just because it is now the only measured category match.
            options = [e for e in options if e.id not in self._binding_peers.get(label, set())]
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
        ) if source_reference and not re.search(
            r"\bfrom (?:the )?table cent(?:er|re)\b", source_clause,
            flags=re.IGNORECASE,
        ) else None
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
                    if (all(min(e.upper[i], anchor.upper[i]) > max(e.lower[i], anchor.lower[i]) for i in (0, 1))
                        if predicate == "on" else
                        all(anchor.lower[i] - 0.02 <= e.xyz[i] <= anchor.upper[i] + 0.02 for i in (0, 1)))
                    and (
                        abs(e.lower[2] - anchor.upper[2]) <= 0.06
                        if predicate == "on"
                        else e.upper[2] >= anchor.lower[2] - 0.04
                        and e.lower[2] <= anchor.upper[2] + 0.06
                    )
                ]
            return supported[0] if len(supported) == 1 else None
        if source_reference and re.search(r"\btable cent(?:er|re)\b", phrase):
            # A bowl on another measured object is not the one requested
            # from the tabletop.  Resolve that explicit support reference
            # before estimating a centre from the other objects' extents.
            observed = set(relations(visible))
            tabletop = [
                e for e in options
                if not any(
                    f"rel {e.id} {predicate} {anchor.id}" in observed
                    for anchor in visible
                    if anchor.id != e.id and anchor.name != "table"
                    for predicate in ("on", "in")
                )
            ]
            if len(tabletop) == 1:
                return tabletop[0]
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

    def _collective_source(
        self, goal: list, goals: list, entities: list[Entity], held: str | None,
        phrase: str, axes: tuple,
    ) -> tuple[bool, Entity | None]:
        """Treat an explicit collective reference as a measured object set."""
        kind = _kind(goal[1])
        if len(goal) != 3 or goal[0] not in ("on", "in") or not re.search(
            rf"\b(?:both|all|the two)\s+{re.escape(kind)}s?\b", phrase, re.IGNORECASE
        ):
            return False, None
        group = [g for g in goals if len(g) == 3 and g[0] == goal[0]
                 and g[2] == goal[2] and _kind(g[1]) == kind]
        options = [e for e in entities if e.visible and e.name == kind]
        target = self.bind(goal[2], entities, phrase, axes, source_reference=False)
        if len(group) < 2 or len(options) != len(group) or target is None:
            return True, None
        if held is not None:
            return True, next((e for e in options if e.id == held), None)
        observed = set(relations([*options, target]))
        remaining = [e for e in options
                     if f"rel {e.id} {goal[0]} {target.id}" not in observed]
        # Any member can be moved first.  Bind by public measured distance,
        # independent of the private goal's instance suffix or entity IDs.
        return True, min(remaining, key=lambda e: (math.dist(e.xyz, target.xyz), e.xyz), default=None)

    @staticmethod
    def _recover_missing(
        choices: list[Candidate], receipts: list[dict], *, initial_missing: bool = False
    ) -> Candidate | None:
        """Clear the camera view and remeasure once before unresolved help."""
        if not receipts and not initial_missing:
            return None
        previous = receipts[-1].get("tool") if receipts else None
        if previous == "reperceive":
            return None
        recovery = "reperceive" if previous == "retreat" else "retreat"
        return next((c for c in choices if c.tool == recovery), None)

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
            collective, obj = self._collective_source(
                goal, status["goals"], entities, held, clause, axes
            )
            if not collective:
                obj = self.bind(symbol, entities, source_phrase, axes)
            self.last_binding = {
                "goal_kind": predicate,
                "source_entity": obj.id if obj else None,
                "basis": ("collective_measured_set" if collective
                          else "measured_category_extent_and_instruction_relation"),
            }
            if obj is None:
                if predicate in ("open", "close") and _kind(symbol) in ("cabinet", "drawer"):
                    cabinets = [e for e in entities if e.visible and e.name == "cabinet"]
                    if len(cabinets) == 1:
                        coarse = next((c for c in choices if c.tool == "articulate"
                                       and c.object == cabinets[0].id and c.mode == predicate), None)
                        if coarse is not None:
                            # The existing executor preserves the public
                            # top/middle/bottom phrase for cabinet articulation.
                            # This does not invent a drawer pose for placement.
                            self.last_binding["source_entity"] = cabinets[0].id
                            self.last_binding["basis"] = "unique_measured_cabinet_public_drawer_instruction"
                            return coarse
                kind = _kind(symbol)
                recovery = self._recover_missing(
                    choices, receipts,
                    initial_missing=not any(e.visible and (kind == e.name or kind in e.name)
                                            for e in entities),
                )
                if recovery is not None:
                    return recovery
                break
            if not collective:
                self._bindings[symbol] = obj.id
                self._binding_peers.setdefault(symbol, {
                    e.id for e in entities if e.visible and e.name == obj.name and e.id != obj.id
                })
            if predicate in ("on", "in") and len(goal) == 3:
                target = self.bind(goal[2], entities, clause, axes, source_reference=False)
                self.last_binding["target_entity"] = target.id if target else None
                if target is None:
                    if predicate == "in" and status.get("storage_open", {}).get(goal[2]) is False:
                        cabinets = [e for e in entities if e.visible and e.name == "cabinet"]
                        if len(cabinets) == 1:
                            coarse = next((c for c in choices if c.tool == "articulate"
                                           and c.object == cabinets[0].id and c.mode == "open"), None)
                            if coarse is not None and not any(
                                r.get("tool") == "articulate" and r.get("object") == cabinets[0].id
                                and r.get("mode") == "open" for r in receipts
                            ):
                                self.last_binding["basis"] = "closed_storage_measured_cabinet_open_before_interior_measurement"
                                return coarse
                    recovery = self._recover_missing(choices, receipts)
                    if recovery is not None:
                        return recovery
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
