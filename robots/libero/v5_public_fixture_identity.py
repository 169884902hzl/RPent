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


def canonical_stove_measurements(entities, current_step: int, current_ids: set[str],
                                clouds_by_view: Mapping, masks: Mapping, camera: str):
    """Remove only same-capture near-identical stove surfaces, preserving IDs."""
    import numpy as np

    scene = _scene(entities)
    records = {}
    for entity in scene:
        if entity.name != "stove" or entity.id not in current_ids or not _current(entity, current_step):
            continue
        view = clouds_by_view.get(entity.id, {}).get(camera, {})
        points = view.get("xyz_world")
        if (view.get("src") != "perception" or view.get("source_step") != current_step
                or points is None):
            continue
        points = np.asarray(points, dtype="<f8")
        if points.ndim != 2 or points.shape[1] != 3 or len(points) < 30 or not np.isfinite(points).all():
            continue
        packed = np.ascontiguousarray(points).view([("x", "<f8"), ("y", "<f8"), ("z", "<f8")]).reshape(-1)
        records[entity.id] = np.unique(packed)
    kept, aliases = [], []
    for entity in sorted((item for item in scene if item.id in records),
                         key=lambda item: (-len(records[item.id]), item.id)):
        for other in kept:
            if min(_xy_coverage(entity, other), _xy_coverage(other, entity)) < .8:
                continue
            shared = len(np.intersect1d(records[entity.id], records[other.id]))
            point_coverage = shared / min(len(records[entity.id]), len(records[other.id]))
            first, second = masks.get(entity.id), masks.get(other.id)
            mask_coverage = None
            if (first is not None and second is not None and first.shape == second.shape
                    and min(np.count_nonzero(first), np.count_nonzero(second)) > 0):
                mask_coverage = float(np.count_nonzero(first & second)
                                      / min(np.count_nonzero(first), np.count_nonzero(second)))
            if point_coverage >= .98 or (mask_coverage is not None and mask_coverage >= .98):
                aliases.append({"alias": entity.id, "representative": other.id,
                                "camera": camera, "source_step": current_step,
                                "smaller_public_cloud_coverage": point_coverage,
                                "smaller_actual_mask_coverage": mask_coverage,
                                "reason": "same_capture_same_category_nested_surface"})
                break
        else:
            kept.append(entity)
    removed = {item["alias"] for item in aliases}
    removed.update(entity.id for entity in scene if entity.part_of in removed)
    return {entity.id: entity for entity in scene if entity.id not in removed}, {
        "version": "public_stove_surface_identity/1-dev", "source": "perception",
        "source_step": current_step, "camera": camera, "aliases": aliases,
        "removed_ids": sorted(removed), "current_ids": sorted(current_ids),
        "private_truth_used": False, "new_geometry_created": False,
    }


def stove_point_operating_area(entity: Entity, points, eef_xyz, *, radius_m: float = 1.) -> dict:
    """Require the measured centre and most points inside the public XY area."""
    import numpy as np

    evidence = {"version": "public_stove_point_operating_area/1-dev",
                "radius_m": radius_m, "min_point_support": .90,
                "median_xy_distance_m": None, "point_support_fraction": None,
                "disposition": "unmeasured", "rejection_reason": "current_public_points_missing"}
    if points is None or eef_xyz is None:
        return evidence
    array, eef = np.asarray(points, dtype=float), np.asarray(eef_xyz, dtype=float)
    if (array.ndim != 2 or array.shape[1] != 3 or len(array) < 30
            or eef.shape != (3,) or not np.isfinite(array).all() or not np.isfinite(eef).all()):
        return evidence
    centre_distance = float(np.linalg.norm(np.asarray(entity.xyz[:2]) - eef[:2]))
    support = float(np.mean(np.linalg.norm(array[:, :2] - eef[:2], axis=1) <= radius_m))
    evidence.update(median_xy_distance_m=centre_distance, point_support_fraction=support,
                    measured_points=len(array))
    if centre_distance > radius_m or support < evidence["min_point_support"]:
        evidence.update(disposition="rejected", rejection_reason="outside_public_point_supported_operating_area")
    else:
        evidence.update(disposition="eligible", rejection_reason=None)
    return evidence
