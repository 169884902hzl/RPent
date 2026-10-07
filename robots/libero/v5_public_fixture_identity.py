"""Reject publicly proven fixture aliases; retain genuinely unresolved peers.

This is an owned development helper. It reads only perception entities and an
explicit capture number, does not move IDs, and never inspects a task predicate.
Its result should be applied before state/candidate rendering, not after choice.
"""

from collections.abc import Mapping, Sequence
import math

from robots.libero.v5_state import Entity


VERSION = "public_fixture_surface_alias/2-dev"


def placement_target_moves(entity: Entity | None) -> bool:
    """A measured drawer/door part is not a stationary placement support."""
    return bool(entity and (any(word in entity.name.lower().split() for word in ("drawer", "door"))
                           or entity.geometry in ("measured_front_band", "measured_door_surface")))


def _scene(entities: Sequence[Entity] | Mapping[str, Entity]) -> list[Entity]:
    return list(entities.values()) if isinstance(entities, Mapping) else list(entities)


def _xy_coverage(first: Entity, second: Entity) -> float:
    area = math.prod(max(first.upper[i] - first.lower[i], 0.) for i in (0, 1))
    if area <= 0:
        return 0.
    common = math.prod(max(0., min(first.upper[i], second.upper[i])
                           - max(first.lower[i], second.lower[i])) for i in (0, 1))
    return common / area


def _current(entity: Entity, step: int) -> bool:
    return entity.visible and entity.source_step == step


def _same_volume(first: Entity, second: Entity) -> bool:
    """An independently segmented drawer has to measure the same fragment."""
    return (_xy_coverage(first, second) >= .85 and _xy_coverage(second, first) >= .85
            and all(abs(first.lower[i] - second.lower[i]) <= .01
                    and abs(first.upper[i] - second.upper[i]) <= .01 for i in range(3)))


def canonical_fixture_scene(entities, current_step: int, *, allow_drawer_fragment_alias: bool = False):
    """Return a scene copy without measured top aliases or confirmed drawer fragments.

    A same-category entity is not enough reason to remove it. Cabinet
    fragments require a separate *current* drawer measurement plus its unique
    current cabinet association. Horizontal drawer aliases require a real
    measured cabinet top with an explicit parent; no full box is synthesized.
    """
    if not isinstance(current_step, int) or current_step < 0:
        raise ValueError("current capture step must be a nonnegative integer")
    scene = _scene(entities)
    by_id = {entity.id: entity for entity in scene}
    if len(by_id) != len(scene):
        raise ValueError("duplicate public entity IDs cannot be canonicalized")
    rejected = {}
    current_cabinets = [e for e in scene if e.name == "cabinet" and _current(e, current_step)]
    tops = [e for e in scene if e.name == "cabinet top surface"
            and e.geometry == "measured_top_surface" and e.part_of in by_id
            and by_id[e.part_of].name == "cabinet"
            and _current(e, current_step) and _current(by_id[e.part_of], current_step)]
    for drawer in (e for e in scene if e.name == "drawer" and not e.part_of):
        thickness = drawer.upper[2] - drawer.lower[2]
        if not 0 < thickness <= .01:
            continue
        matches = [top for top in tops if _xy_coverage(drawer, top) >= .90
                   and abs(drawer.upper[2] - top.upper[2]) <= .005
                   and drawer.lower[2] >= top.lower[2] - .005]
        if len(matches) == 1:
            rejected[drawer.id] = {"alias": drawer.id, "measured_surface": matches[0].id,
                "parent": matches[0].part_of, "reason": "thin_horizontal_drawer_is_measured_top_surface",
                "thickness_m": thickness, "xy_coverage": _xy_coverage(drawer, matches[0]),
                "alias_source_step": drawer.source_step,
                "surface_source_step": matches[0].source_step}
    drawers = [e for e in scene if e.name == "drawer" and _current(e, current_step)
               and e.id not in rejected and e.upper[2] - e.lower[2] > .01]
    for fragment in (e for e in scene if allow_drawer_fragment_alias
                     and e.name == "cabinet"):
        independent = [drawer for drawer in drawers if _same_volume(fragment, drawer)]
        if len(independent) != 1:
            continue
        drawer = independent[0]
        # A segmentation that is itself as tall as its cabinet has not
        # demonstrated a part/shell distinction, so keep that ambiguity.
        matches = []
        for parent in current_cabinets:
            if parent.id == fragment.id:
                continue
            gap = math.sqrt(sum(max(0., parent.lower[i] - drawer.upper[i],
                                     drawer.lower[i] - parent.upper[i]) ** 2 for i in (0, 1)))
            drawer_height = drawer.upper[2] - drawer.lower[2]
            parent_height = parent.upper[2] - parent.lower[2]
            if (gap <= .25 and parent.lower[2] - .02 <= drawer.xyz[2] <= parent.upper[2] + .02
                    and 0 < drawer_height <= .5 * parent_height):
                matches.append(parent)
        if len(matches) == 1:
            rejected[fragment.id] = {"alias": fragment.id, "current_drawer": drawer.id,
                "parent": matches[0].id,
                "reason": ("current_cabinet_fragment_independently_measured_as_drawer"
                           if _current(fragment, current_step) else
                           "cached_cabinet_fragment_independently_measured_as_drawer"),
                "alias_source_step": fragment.source_step, "drawer_source_step": drawer.source_step,
                "mutual_xy_coverage": [_xy_coverage(fragment, drawer), _xy_coverage(drawer, fragment)]}
    removed = set(rejected)
    # Derived parts of a rejected semantic parent cannot remain advertised as
    # separate cabinets or measured stationary supports.
    removed.update(e.id for e in scene if e.part_of in rejected)
    result = {e.id: e for e in scene if e.id not in removed}
    evidence = {"version": VERSION, "source": "perception", "source_step": current_step,
        "drawer_fragment_alias_enabled": allow_drawer_fragment_alias,
        "aliases": list(rejected.values()), "removed_ids": sorted(removed),
        "retained_stale_ids": sorted(e.id for e in scene if not _current(e, current_step) and e.id not in removed),
        "private_truth_used": False, "new_geometry_created": False, "selected_id_retargeted": False}
    return result, evidence
