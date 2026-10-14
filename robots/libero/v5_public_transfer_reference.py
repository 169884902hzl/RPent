# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Resolve transfer references from instruction text and measured entities."""

from __future__ import annotations

import math
import re

from robots.libero.v5_state import Entity

_ALIASES = {"bowl": ("akita black bowl", "black bowl"), "porcelain mug": ("white mug",),
            "white yellow mug": ("yellow and white mug", "white and yellow mug"),
            "frypan": ("frying pan",), "barbecue sauce": ("bbq sauce",)}


def _named(phrase: str, entities: list[Entity]) -> list[Entity]:
    matches = []
    for entity in entities:
        if not entity.visible and not (entity.geometry or '').startswith('cached_perception'):
            continue
        names = (entity.name, *_ALIASES.get(entity.name, ()))
        lengths = [len(name) for name in names if re.search(r'\b' + re.escape(name) + r'\b', phrase)]
        if lengths:
            matches.append((max(lengths), entity))
    if not matches:
        return []
    best = max(length for length, _ in matches)
    return [entity for length, entity in matches if length == best]


def _reference(phrase: str, entities: list[Entity], axes: tuple,
               *, candidates: list[Entity] | None = None) -> Entity | None:
    options = _named(phrase, entities) if candidates is None else candidates
    if not options:
        return None
    between = re.search(r'\b(not )?between (?:the )?(.+?) and (?:the )?(.+)$', phrase)
    if between:
        anchors = [_reference(between[i], entities, axes) for i in (2, 3)]
        if any(anchor is None for anchor in anchors):
            return None
        first, second = anchors
        delta = [second.xyz[i] - first.xyz[i] for i in (0, 1)]
        norm = sum(value * value for value in delta)
        if norm < .0025:
            return None
        retained = []
        for entity in options:
            fraction = sum((entity.xyz[i] - first.xyz[i]) * delta[i] for i in (0, 1)) / norm
            distance = math.dist(entity.xyz[:2], [first.xyz[i] + fraction * delta[i] for i in (0, 1)])
            is_between = 0 < fraction < 1 and distance <= .04
            if is_between != bool(between[1]):
                retained.append(entity)
        return retained[0] if len(retained) == 1 else None
    relation = re.search(r'\b(next to|near|on|in|inside) (?:the )?(.+)$', phrase)
    if relation:
        anchor_phrase = re.sub(r'^(?:top of (?:the )?|top surface of (?:the )?)', '', relation[2])
        anchor = _reference(anchor_phrase, entities, axes)
        if anchor is None:
            return None
        options = [entity for entity in options if entity.id != anchor.id]
        if relation[1] in ('next to', 'near'):
            ranked = sorted(options, key=lambda entity: math.dist(entity.xyz[:2], anchor.xyz[:2]))
            if ranked and (len(ranked) == 1 or math.dist(ranked[1].xyz[:2], anchor.xyz[:2])
                           - math.dist(ranked[0].xyz[:2], anchor.xyz[:2]) > .02):
                return ranked[0]
            return None
        supported = [entity for entity in options
                     if all(min(entity.upper[i], anchor.upper[i]) > max(entity.lower[i], anchor.lower[i])
                            for i in (0, 1))
                     and (abs(entity.lower[2] - anchor.upper[2]) <= .06 if relation[1] == 'on'
                          else entity.lower[2] <= anchor.upper[2] + .02
                          and entity.upper[2] >= anchor.lower[2] - .02)]
        return supported[0] if len(supported) == 1 else None
    right, front = axes
    if re.search(r'\bmiddle\b', phrase):
        if len(options) < 3 or len(options) % 2 == 0:
            return None
        ranked = sorted(options, key=lambda entity: sum(entity.xyz[i] * right[i] for i in range(3)))
        mid = len(ranked) // 2
        if all(abs(sum((ranked[mid].xyz[i] - ranked[other].xyz[i]) * right[i] for i in range(3))) > .02
               for other in (mid - 1, mid + 1)):
            return ranked[mid]
        return None
    if len(options) == 1:
        # One visible class member establishes a name, not an ordinal rank.
        if re.search(r'\b(?:left|right|front|back)(?:most)?\b', phrase):
            return None
        return options[0]
    for word, axis, sign in (('left', right, -1), ('right', right, 1),
                             ('front', front, 1), ('back', front, -1)):
        if re.search(r'\b' + word + r'(?:most)?\b', phrase):
            ranked = sorted(options, key=lambda entity: sign * sum(entity.xyz[i] * axis[i] for i in range(3)), reverse=True)
            gap = abs(sum((ranked[0].xyz[i] - ranked[1].xyz[i]) * axis[i] for i in range(3)))
            return ranked[0] if gap > .02 else None
    return None


def transfer_reference(entities: list[Entity], instruction: str, view_axes: tuple | None = None) -> dict:
    """Resolve a single transfer; unknown references leave normal options available.

    A put/place destination is removed before source resolution. In pick-and-
    place language the pick clause supplies source relations. The output only
    prioritizes existing typed candidates; it does not insert coordinates.
    """
    text = instruction.lower().strip().rstrip('.')
    axes = view_axes or ((1, 0, 0), (0, -1, 0))
    clauses = re.split(r'\s+and\s+(?:place|put)\s+(?:it|them)\b|\s+then\s+(?:place|put)\s+(?:it|them)\b', text, maxsplit=1)
    source_phrase = clauses[0]
    destination_clause = clauses[1] if len(clauses) == 2 else text
    relations = list(re.finditer(r'\s+(on|in|into|inside)\s+', destination_clause))
    if not relations:
        return {'source': None, 'target': None, 'mode': None}
    destination = relations[-1]
    target_phrase = destination_clause[destination.end():]
    if len(clauses) == 1:
        if not re.match(r'(?:put|place)\b', text):
            return {'source': None, 'target': None, 'mode': None}
        source_phrase = text[:destination.start()]
    # An anchor mentioned in a source relation must not become another source
    # merely because its full category name is longer than the source noun.
    noun_phrase = re.split(r'\b(?:not between|between|next to|near|on|in|inside)\b', source_phrase, maxsplit=1)[0]
    source_options = _named(noun_phrase, entities)
    source = None
    if source_options:
        source = _reference(source_phrase, entities, axes, candidates=source_options)
    target = _reference(target_phrase, entities, axes)
    return {'source': source.id if source else None, 'target': target.id if target else None,
            'mode': 'on' if destination[1] == 'on' else 'in',
            'source_phrase': source_phrase, 'target_phrase': target_phrase}
