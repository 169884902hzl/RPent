# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Finite contact subtasks rendered only from public measured entities.

This module has no oracle, asset or task-file input. BDDL progress predicates
belong to the separate original-task collection side, never these candidates.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from robots.libero.v5_state import Candidate, Entity, fixture_actions

TRANSFER_MODES = ("on", "in")
FIXTURE_MODES = ("open", "close", "turn_on", "turn_off")
PROMPT_VERSION = "measured-libero-subtask/1"
_ALIASES = {"frypan": "frying pan", "barbecue sauce": "bbq sauce"}


def _entities(entities: Sequence[Entity] | Mapping[str, Entity]) -> list[Entity]:
    return list(entities.values()) if isinstance(entities, Mapping) else list(entities)


def subtask_phrase(source_name: str, mode: str, target_name: str | None = None) -> str:
    """Use the same legal category template in preparation and at runtime."""
    source = _ALIASES.get(source_name, source_name)
    if mode in TRANSFER_MODES and target_name is not None:
        return f"put the {source} {mode} the {_ALIASES.get(target_name, target_name)}"
    if mode in FIXTURE_MODES and target_name is None:
        return f"{mode.replace('_', ' ')} the {source}"
    raise ValueError("unsupported subtask template argument shape")


def subtask_prompt(action: Candidate, entities: Sequence[Entity] | Mapping[str, Entity]) -> str:
    """Render a selected typed subtask, without instruction or private goals."""
    if action.tool != "vla_subtask":
        raise ValueError("expected a typed vla_subtask candidate")
    measured = {e.id: e for e in _entities(entities)}
    if action.object not in measured:
        raise ValueError("subtask source has no measured entity")
    source = measured[action.object]
    if action.mode in TRANSFER_MODES:
        if action.target not in measured or action.object == action.target:
            raise ValueError("transfer subtask needs a distinct measured target")
        target = measured[action.target]
        return subtask_phrase(source.name, action.mode, target.name)
    if action.mode in FIXTURE_MODES and action.target is None:
        if action.mode not in fixture_actions(source.name):
            raise ValueError("fixture subtask is not supported by this measured class")
        return subtask_phrase(source.name, action.mode)
    raise ValueError("unsupported typed subtask mode or argument shape")


def subtask_candidates(
    entities: Sequence[Entity] | Mapping[str, Entity], instruction: str,
    eef_xyz: tuple[float, ...], held: str | None, *, limit: int = 6,
) -> list[Candidate]:
    """Enumerate at most six parallel contact macros without goal access.

    The state owner combines these with split primitives and shuffles the
    final bounded candidate list. A macro is a complete transfer/articulation,
    not a request to stop π0.5 at the first nonempty gripper opening.
    """
    if not 0 <= limit <= 6:
        raise ValueError("vla_subtask candidate allowance must be 0..6")
    text = instruction.lower()

    def mentioned(entity: Entity) -> bool:
        return entity.name.lower() in text or _ALIASES.get(entity.name, entity.name).lower() in text

    measured = [e for e in _entities(entities) if e.visible or (
        e.geometry and e.geometry.startswith("cached_perception"))]
    measured.sort(key=lambda e: (not mentioned(e), math.dist(e.xyz, eef_xyz), e.id))
    selected = measured[:8]
    sources = [e for e in selected if not fixture_actions(e.name)
               and e.name != "table" and not e.name.startswith("area ")
               and not e.name.endswith("surface") and held in (None, e.id)]
    options = [Candidate("vla_subtask", e.id, mode=mode)
               for e in selected for mode in fixture_actions(e.name)]
    for source in sources:
        for target in selected:
            if source.id == target.id or target.geometry in ("measured_front_band", "measured_front_surface"):
                continue
            for mode in TRANSFER_MODES:
                if mode == "in" and not any(word in target.name for word in (
                    "bowl", "ramekin", "basket", "drawer", "microwave", "caddy", "compartment", "cabinet")):
                    continue
                options.append(Candidate("vla_subtask", source.id, target.id, mode))
    by_id = {e.id: e for e in selected}

    def priority(action: Candidate) -> tuple:
        source = by_id[action.object]
        target = by_id.get(action.target)
        words = action.mode.replace("_", " ")
        return (not (words in text), not mentioned(source),
                not (mentioned(target) if target is not None else mentioned(source)),
                math.dist(source.xyz, eef_xyz), action.text())

    return sorted(options, key=priority)[:limit]
