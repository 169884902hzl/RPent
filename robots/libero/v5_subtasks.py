# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Finite contact subtasks rendered only from public measured entities.

This module has no oracle, asset or task-file input. BDDL progress predicates
belong to the separate original-task collection side, never these candidates.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from robots.libero.v5_state import Candidate, Entity, fixture_actions, relations

TRANSFER_MODES = ("on", "in")
FIXTURE_MODES = ("open", "close", "turn_on", "turn_off")
PROMPT_VERSION = "measured-libero-subtask/2-selected-instance"
_ALIASES = {"frypan": "frying pan", "barbecue sauce": "bbq sauce"}
_RELATION_THRESHOLD_M = .02


class SubtaskBindingError(ValueError):
    """Public measurements cannot uniquely describe the selected typed ID."""


def _entities(entities: Sequence[Entity] | Mapping[str, Entity]) -> list[Entity]:
    return list(entities.values()) if isinstance(entities, Mapping) else list(entities)


def _name(entity: Entity) -> str:
    return _ALIASES.get(entity.name, entity.name)


def _measured(entity: Entity) -> bool:
    return entity.visible or bool(entity.geometry and entity.geometry.startswith("cached_perception"))


def _ordinal(rank: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
             7: "seventh", 8: "eighth"}
    if rank in words:
        return words[rank]
    suffix = "th" if 10 <= rank % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def measured_instance_description(
    selected: Entity, entities: Sequence[Entity] | Mapping[str, Entity],
    view_axes: tuple[tuple, tuple] | None = None,
) -> str:
    """Describe this ID, never choose a different instance or read a goal.

    Axes and the 2 cm distinction threshold match v5_state.relations. Neutral
    IDs, container iteration order and near-tied coordinates cannot break ties.
    """
    scene = _entities(entities)
    name = _name(selected)
    peers = [entity for entity in scene if _name(entity) == name]
    if not any(entity == selected for entity in peers) or any(not _measured(entity) for entity in peers):
        raise SubtaskBindingError(f"cannot uniquely bind selected {selected.id}: {name} measurement unavailable")
    if len(peers) == 1:
        return name
    right, front = view_axes if view_axes is not None else ((1, 0, 0), (0, -1, 0))
    for axis in (right, front):
        if len(axis) != 3 or not all(math.isfinite(value) for value in axis) or math.hypot(*axis[:2]) == 0 or axis[2] != 0:
            raise ValueError("subtask instance description requires finite planar view axes")
    for axis, origin, extremes in ((right, "left", ("leftmost", "rightmost")),
                                   (tuple(-value for value in front), "front", ("frontmost", "backmost"))):
        positions = sorted(((sum(entity.xyz[i] * axis[i] for i in range(3)), entity.id) for entity in peers),
                           key=lambda item: item[0])
        rank = next(index for index, (_, eid) in enumerate(positions) if eid == selected.id)
        gaps = [positions[index + 1][0] - positions[index][0] for index in range(len(positions) - 1)]
        if rank == 0 and gaps[0] > _RELATION_THRESHOLD_M:
            return f"{extremes[0]} {name}"
        if rank == len(peers) - 1 and gaps[-1] > _RELATION_THRESHOLD_M:
            return f"{extremes[1]} {name}"
        if all(gap > _RELATION_THRESHOLD_M for gap in gaps):
            return f"{_ordinal(rank + 1)} {name} from the {origin}"
    # Existing measured on/in/near relations can distinguish stacked or
    # contained instances when their planar ordering is unresolved.
    measured_relations = {tuple(row.split()[1:]) for row in relations(scene, right_axis=right, front_axis=front)}
    relation_words = {"left_of": "to the left of", "in_front_of": "in front of",
                      "on": "on", "in": "in", "near": "near"}
    names = [_name(entity) for entity in scene]
    for anchor in sorted(scene, key=lambda entity: _name(entity)):
        anchor_name = _name(anchor)
        if not _measured(anchor) or names.count(anchor_name) != 1 or anchor.id == selected.id:
            continue
        for predicate, words in relation_words.items():
            matching = [entity.id for entity in peers if (entity.id, predicate, anchor.id) in measured_relations]
            if matching == [selected.id]:
                return f"{name} that is {words} the {anchor_name}"
    raise SubtaskBindingError(f"cannot uniquely bind selected {selected.id}: {name} has no unique measured description")


def _allows_in(target: Entity) -> bool:
    name = target.name.lower().strip()
    return (not name.endswith("surface") and target.geometry != "measured_top_surface"
            and any(word in name for word in (
                "bowl", "ramekin", "basket", "drawer", "microwave", "caddy", "compartment", "cabinet")))


def subtask_phrase(source_name: str, mode: str, target_name: str | None = None) -> str:
    """Use the same legal category template in preparation and at runtime."""
    source = _ALIASES.get(source_name, source_name)
    if mode in TRANSFER_MODES and target_name is not None:
        return f"put the {source} {mode} the {_ALIASES.get(target_name, target_name)}"
    if mode in FIXTURE_MODES and target_name is None:
        return f"{mode.replace('_', ' ')} the {source}"
    raise ValueError("unsupported subtask template argument shape")


def subtask_prompt(
    action: Candidate, entities: Sequence[Entity] | Mapping[str, Entity],
    view_axes: tuple[tuple, tuple] | None = None,
) -> str:
    """Render this selected typed action; unresolved identity raises SubtaskBindingError."""
    if action.tool != "vla_subtask":
        raise ValueError("expected a typed vla_subtask candidate")
    scene = _entities(entities)
    measured = {e.id: e for e in scene}
    if len(measured) != len(scene):
        raise SubtaskBindingError("cannot uniquely bind subtask: duplicate public entity IDs")
    if action.object not in measured:
        raise ValueError("subtask source has no measured entity")
    source = measured[action.object]
    if action.mode in TRANSFER_MODES:
        if action.target not in measured or action.object == action.target:
            raise ValueError("transfer subtask needs a distinct measured target")
        target = measured[action.target]
        if action.mode == "in" and not _allows_in(target):
            raise ValueError("transfer subtask requires a measured container for in, not a top surface")
        return subtask_phrase(measured_instance_description(source, scene, view_axes), action.mode,
                              measured_instance_description(target, scene, view_axes))
    if action.mode in FIXTURE_MODES and action.target is None:
        if action.mode not in fixture_actions(source.name):
            raise ValueError("fixture subtask is not supported by this measured class")
        return subtask_phrase(measured_instance_description(source, scene, view_axes), action.mode)
    raise ValueError("unsupported typed subtask mode or argument shape")


def subtask_candidates(
    entities: Sequence[Entity] | Mapping[str, Entity], instruction: str,
    eef_xyz: tuple[float, ...], held: str | None, *, limit: int = 6,
    view_axes: tuple[tuple, tuple] | None = None,
) -> list[Candidate]:
    """Enumerate at most six parallel contact macros without goal access.

    The state owner combines these with split primitives and shuffles the
    final bounded candidate list. A macro is a complete transfer/articulation,
    not a request to stop π0.5 at the first nonempty gripper opening.
    Macros without a unique measured binding are omitted; split primitives remain the
    candidate owner's responsibility, without rewriting the selected IDs.
    """
    if not 0 <= limit <= 6:
        raise ValueError("vla_subtask candidate allowance must be 0..6")
    text = instruction.lower()

    def mentioned(entity: Entity) -> bool:
        return entity.name.lower() in text or _ALIASES.get(entity.name, entity.name).lower() in text

    scene = _entities(entities)
    measured = [e for e in scene if _measured(e)]
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
                if mode == "in" and not _allows_in(target):
                    continue
                options.append(Candidate("vla_subtask", source.id, target.id, mode))
    bindable = []
    for action in options:
        try:
            subtask_prompt(action, scene, view_axes)
        except SubtaskBindingError:
            continue
        bindable.append(action)
    by_id = {e.id: e for e in selected}

    def priority(action: Candidate) -> tuple:
        source = by_id[action.object]
        target = by_id.get(action.target)
        words = action.mode.replace("_", " ")
        return (not (words in text), not mentioned(source),
                not (mentioned(target) if target is not None else mentioned(source)),
                math.dist(source.xyz, eef_xyz), action.text())

    return sorted(bindable, key=priority)[:limit]
