# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Perception cache and composite skills using RPent's LIBERO primitives."""

from __future__ import annotations

import base64
import hashlib
import math
import random
import re
import time
from contextlib import nullcontext
from dataclasses import replace

import numpy as np

from robots.libero.v5_state import Candidate, Entity, entity_record, fixture_actions, grasp_verified, place_verified
from robots.libero.v5_env_client import V5SkillEnvClient
from rpent.robots.components.sam3_client import Sam3Client


class WaypointNotReached(RuntimeError):
    """An executed servo stopped outside its measured positional tolerance."""


def category(name: str) -> str:
    """Use scene categories as segmentation vocabulary, stripping instance IDs."""
    text = re.sub(r"\s+\d+$", "", name.replace("_", " ")).strip()
    if "bowl" in text:
        return "bowl"
    if "ramekin" in text:
        return "ramekin"
    if "cookies" in text:
        return "cookie box"
    # Keep the public vocabulary aligned with the nouns used by the original
    # LIBERO task language.  These are visual labels only; no simulator
    # instance names or goal predicates are exposed.
    aliases = {
        "cream cheese box": "cream cheese",
        "bbq sauce": "barbecue sauce",
        "barbecue sauce": "barbecue sauce",
        "chocolate pudding cup": "chocolate pudding",
        "chefmate 8 frypan": "frypan",
        "frypan": "frypan",
    }
    if text in aliases:
        return aliases[text]
    return text


def segmentation_prompt(name: str) -> str:
    """Translate LIBERO category names to visible package descriptions."""
    return {
        "bowl": "black patterned bowl",
        "plate": "white plate with a red rim",
        "alphabet soup": "blue can",
        "tomato sauce": "red tomato sauce can",
        "salad dressing": "salad dressing bottle with a green cap",
        "ketchup": "ketchup bottle with a gray cap",
        "cream cheese": "blue cream cheese package",
        "barbecue sauce": "brown barbecue sauce bottle with an orange cap",
        "butter": "small red box",
        "milk": "carton labeled Milk",
        "chocolate pudding": "flat brown box",
        "porcelain mug": "gray textured mug",
        "cabinet": "cabinet",
        "drawer": "open drawer of the small cabinet",
        "microwave": "microwave door",
        "ramekin": "small gray ribbed bowl",
        "cookie box": "red and white checkered box",
        "moka pot": "silver moka coffee pot",
        "red coffee mug": "red ceramic coffee mug",
        "white yellow mug": "white and yellow ceramic mug",
        "black book": "black book on the tabletop",
        "basket": "white woven storage basket",
        "rack": "wooden slatted rack",
        "caddy": "brown desk organizer with compartments",
        "frypan": "black frying pan",
        "stove": "single electric stove",
        "wine bottle": "green wine bottle",
        "table": "wooden tabletop",
    }.get(name, name)


def scene_vocabulary(names: list[str], instruction: str) -> list[str]:
    """Use provided scene names; add fixtures explicitly named by the instruction."""
    result = {category(name) for name in names}
    for fixture in ("drawer", "cabinet", "microwave", "stove", "rack", "caddy", "compartment", "basket"):
        if re.search(r"\b" + fixture + r"\b", instruction, re.IGNORECASE):
            result.add(fixture)
    if "drawer" in result:
        result.add("cabinet")
    if re.search(r"\btable cent(?:er|re)\b", instruction, re.IGNORECASE):
        result.add("table")
    return sorted(result)


def instruction_noun_phrases(instruction: str) -> list[str]:
    """Extract bounded article-led noun phrases with deterministic stop words."""
    stop = {"and", "then", "on", "in", "into", "from", "to", "of", "with", "at", "that",
            "is", "are", "put", "place", "pick", "close", "open", "turn"}
    phrases = []
    for match in re.finditer(r"(?=\b(?:the|an|a)\s+([a-z][a-z -]*))", instruction.lower()):
        words = []
        for word in match[1].split():
            if word in stop or len(words) == 5:
                break
            words.append(word)
        if words:
            phrases.append(" ".join(words))
    return list(dict.fromkeys(phrases))[:8]


def instruction_regions(instruction: str) -> list[tuple[str, str]]:
    """Name only explicitly requested spatial destinations."""
    return list(dict.fromkeys(re.findall(
        r"\b(front|back|left|right) of (?:the )?(stove|plate)\b", instruction.lower()
    )))


def region_name(direction: str, anchor: str) -> str:
    return f"area {direction} of {anchor}"


def segmentation_retry_prompt(name: str) -> str:
    """Use a concrete visual synonym when the first open-vocabulary query is empty."""
    return {
        "bowl": "black bowl on the tabletop",
        "plate": "white plate with red rings",
        "cookie box": "small box of cookies",
        "ramekin": "silver ramekin below the black bowl",
        "cabinet": "cabinet with drawers and handles",
        "drawer": "drawer",
        "microwave": "open microwave door",
        "cream cheese": "small blue rectangular cream cheese box",
        "barbecue sauce": "barbecue sauce bottle",
        "butter": "red butter box",
        "milk": "milk carton",
        "chocolate pudding": "brown rectangular box",
        "porcelain mug": "white textured mug",
        "red coffee mug": "red mug",
        "white yellow mug": "white and yellow mug",
        "black book": "black book",
        "basket": "white woven basket",
        "rack": "wooden slatted rack",
        "caddy": "brown organizer tray with compartments",
        "frypan": "black frying pan",
        "stove": "red stove burner",
        "wine bottle": "wine bottle",
        "moka pot": "silver octagonal coffee maker",
        "table": "wooden tabletop",
    }.get(name, segmentation_prompt(name))


class MeasuredScene:
    """Stable episode-local IDs bound only to distinct measured instances."""

    def __init__(self, toolkit, rpc, seed: int, *, furniture_parts_v1: bool = False,
                 instruction_queries_v1: bool = False, wrist_recall_v1: bool = False,
                 fixture_support_filter_v1: bool = False, fixture_front_geometry_v1: bool = False,
                 fixture_identity_cache_v1: bool = False,
                 dual_view_fusion_v1: bool = False, shape_fit_v1: bool = False,
                 fusion_depth_trim_v2: bool = False,
                 shape_completion_v2: bool = False, occluded_measurement_cache_v2: bool = False,
                 fixture_drawer_clouds_v2: bool = False,
                 fixture_part_visibility_v2: bool = False,
                 fixture_handle_geometry_v3: bool = False,
                 fixture_endpoint_geometry_v3: bool = False,
                 microwave_recall_geometry_v3: bool = False,
                 microwave_instance_geometry_v4: bool = False,
                 appliance_support_crop_v5: bool = False,
                 microwave_door_cloud_v6: bool = False, door_point_recall_v7: bool = False,
                 door_plane_consensus_v1: bool = False,
                 region_anchor_cache_v1: bool = False,
                 record_sam_masks_v6: bool = False) -> None:
        self.toolkit = toolkit
        self.rpc = rpc
        self.instruction = ""
        self.entities: dict[str, Entity] = {}
        self.vocabulary: set[str] = set()
        self.instance_limits: dict[str, int] = {}
        self.calls = 0
        self.perception_s = 0.0
        self.last_measurement_s: dict[str, float] = {}
        self._scores: dict[str, float] = {}
        self.furniture_parts_v1 = furniture_parts_v1
        self.instruction_queries_v1 = instruction_queries_v1
        self.wrist_recall_v1 = wrist_recall_v1
        self.fixture_support_filter_v1 = fixture_support_filter_v1
        self.fixture_front_geometry_v1 = fixture_front_geometry_v1
        self.fixture_identity_cache_v1 = fixture_identity_cache_v1
        self.dual_view_fusion_v1 = dual_view_fusion_v1
        self.fusion_depth_trim_v2 = fusion_depth_trim_v2
        self.shape_fit_v1 = shape_fit_v1
        self.shape_completion_v2 = shape_completion_v2
        self.occluded_measurement_cache_v2 = occluded_measurement_cache_v2
        self.fixture_drawer_clouds_v2 = fixture_drawer_clouds_v2
        self.fixture_part_visibility_v2 = fixture_part_visibility_v2
        self.fixture_handle_geometry_v3 = fixture_handle_geometry_v3
        self.fixture_endpoint_geometry_v3 = fixture_endpoint_geometry_v3
        self._drawer_endpoint_anchors = {}
        self._microwave_frame_anchors = {}
        self.microwave_recall_geometry_v3 = microwave_recall_geometry_v3
        self.microwave_instance_geometry_v4 = microwave_instance_geometry_v4
        self.appliance_support_crop_v5 = appliance_support_crop_v5
        self.microwave_door_cloud_v6 = microwave_door_cloud_v6
        self.door_point_recall_v7 = door_point_recall_v7
        self.door_plane_consensus_v1 = door_plane_consensus_v1
        self.region_anchor_cache_v1 = region_anchor_cache_v1
        self.record_sam_masks_v6 = record_sam_masks_v6
        self.region_anchors: dict[str, Entity] = {}
        self.work_surface_measurement = None
        self.perception_evidence: dict[str, dict] = {}
        self.measurement_clouds: dict[str, np.ndarray] = {}
        self._rejected_fixture_entities: dict[str, Entity] = {}
        self.fixture_front_axes = {}
        self.support_z = None
        self.fixture_measurement_evidence: dict[str, dict] = {}
        self.rejected_fixture_measurements: list[dict] = []
        self._ids = [f"e{i}" for i in range(1, 129)]
        random.Random(seed).shuffle(self._ids)
        meta = toolkit._state.load("agentview_metadata.json")
        rotation = np.asarray(meta["extrinsic_cam2world"], dtype=float)[:3, :3]
        axes = []
        for column in (0, 1):
            axis = rotation[:, column].copy()
            axis[2] = 0
            norm = np.linalg.norm(axis)
            if norm < 1e-6:
                raise ValueError("camera cannot define a planar relation axis")
            axes.append(tuple(float(round(x / norm, 6)) for x in axis))
        self.view_axes = tuple(axes)

    def refresh(self, names: list[str], *, placement: tuple[Entity, Entity] | None = None,
                camera_view: str | None = None, guided_entity: Entity | None = None) -> None:
        """Segment only requested categories from a freshly captured RGB-D frame."""
        started = time.perf_counter()
        self.vocabulary.update(names)
        if "moka pot" in names and "frypan" in self.vocabulary and placement is None:
            # A coffee-pot query can include the adjacent pan. Obtain the
            # exclusion mask from this same frame, never from a cached pose.
            names = list(dict.fromkeys([*names, "frypan"]))
        state = self.toolkit._state
        camera = camera_view or ("wrist" if placement else "agentview")
        image = state.load_bytes(f"{camera}_high.png")
        world = state.load(f"{camera}_world_high.npz")
        encoded = base64.b64encode(image).decode("ascii")
        category_masks = {}
        instance_masks = {}
        secondary_masks = {}
        secondary_camera = "wrist" if camera == "agentview" else "agentview"
        secondary_world = state.load(f"{secondary_camera}_world_high.npz") if self.dual_view_fusion_v1 else None
        secondary_image = base64.b64encode(state.load_bytes(f"{secondary_camera}_high.png")).decode("ascii") if self.dual_view_fusion_v1 else None
        measured_names = sorted(n for n in set(names) if not n.startswith("area "))
        if self.microwave_recall_geometry_v3:
            # Obtain object footprints before estimating their connected
            # support plane. The plane is cached while stationary.
            measured_names.sort(key=lambda name: name == "microwave")
        for name in measured_names:
            prompt = segmentation_prompt(name)
            if placement and name in ("alphabet soup", "tomato sauce"):
                # After release only the can's lid may remain visible. Its
                # identity comes from the verified grasp and selected placement;
                # associate only a unique measurement in that measured target.
                prompt = "top of a can"
            reply = self.rpc.call(
                "sam3.segment_all",
                kwargs={
                    "image_base64": encoded,
                    "text_prompt": prompt,
                    "min_score": 0.5,
                },
                timeout_s=120,
            )
            self.calls += 1
            if self.microwave_recall_geometry_v3 and name == "microwave":
                from robots.libero.v5_perception_geometry import measured_work_surface
                if self.work_surface_measurement is None:
                    anchors = [e for e in self.entities.values() if e.visible and not e.part_of
                               and not e.name.startswith("area ")
                               and e.name not in ("cabinet", "microwave", "stove", "drawer", "rack", "table")]
                    surface = measured_work_surface(world, anchors)
                    if surface is not None:
                        self.work_surface_measurement = {**surface, "source_step": state.latest_step,
                                                         "camera": camera, "source": "perception"}
                if self.work_surface_measurement is not None:
                    for phrase in ("black rectangular frame", "appliance"):
                        alternative = self.rpc.call("sam3.segment_all", kwargs={
                            "image_base64": encoded, "text_prompt": phrase, "min_score": .25}, timeout_s=120)
                        self.calls += 1
                        reply["instances"] = [*reply.get("instances", []), *[
                            {**item, "geometry_query": phrase} for item in alternative.get("instances", [])]]
            if self.instruction_queries_v1 and placement is None:
                for phrase in instruction_noun_phrases(self.instruction):
                    if category(phrase) != name and not phrase.endswith(name):
                        continue
                    if phrase == prompt:
                        continue
                    alternative = self.rpc.call("sam3.segment_all", kwargs={"image_base64":encoded,
                                                "text_prompt":phrase, "min_score":.35}, timeout_s=120)
                    self.calls += 1
                    reply["instances"] = [*reply.get("instances", []), *alternative.get("instances", [])]
            if not reply.get("instances"):
                retry_prompt = segmentation_retry_prompt(name)
                reply = self.rpc.call(
                    "sam3.segment_all",
                    kwargs={
                        "image_base64": encoded,
                        "text_prompt": retry_prompt,
                        "min_score": 0.35,
                    },
                    timeout_s=120,
                )
                self.calls += 1
            if not reply.get("instances"):
                low_prompt = {
                    "stove": "black burner",
                    "moka pot": "coffee pot",
                    "basket": "woven basket",
                    "rack": "wooden rack",
                    "caddy": "desk organizer",
                    "cream cheese": "blue box",
                    "ramekin": "small gray ribbed bowl",
                }.get(name)
                if low_prompt:
                    reply = self.rpc.call(
                        "sam3.segment_all",
                        kwargs={
                            "image_base64": encoded,
                            "text_prompt": low_prompt,
                            "min_score": 0.25,
                        },
                        timeout_s=120,
                    )
                    self.calls += 1
            if not reply.get("instances") and guided_entity is not None and name == guided_entity.name:
                from robots.libero.v5_perception_geometry import (
                    measured_points, measured_prompt_pixel, refinement_mask_matches,
                )
                point = measured_prompt_pixel(world, guided_entity.lower, guided_entity.upper)
                if point is not None:
                    guided = self.rpc.call("sam3.segment", kwargs={
                        "image_base64": encoded, "point": point, "min_score": .5}, timeout_s=120)
                    self.calls += 1
                    if guided.get("found"):
                        mask = Sam3Client._decode_result(guided).mask
                        if mask is not None and mask.shape == world.shape[:2]:
                            points = measured_points(world, mask)
                            if refinement_mask_matches(points, guided_entity.lower, guided_entity.upper):
                                guided["guidance"] = {"method": "prior_measured_bounds_current_rgbd_point/3",
                                                      "camera": camera, "point": point,
                                                      "prior_step": guided_entity.source_step}
                                reply = {"instances": [guided]}
            secondary = []
            if self.dual_view_fusion_v1:
                from robots.libero.v5_perception_geometry import measured_points
                second_reply = self.rpc.call("sam3.segment_all", kwargs={
                    "image_base64": secondary_image, "text_prompt": prompt, "min_score": .35}, timeout_s=120)
                self.calls += 1
                masks = []
                for item in second_reply.get("instances", []):
                    mask = Sam3Client._decode_result(item).mask
                    if mask is None or mask.shape != secondary_world.shape[:2]:
                        raise ValueError("secondary SAM/depth dimensions differ")
                    if self.microwave_instance_geometry_v4 and name == "microwave":
                        from robots.libero.v5_perception_geometry import appliance_foreground_mask, same_segmented_instance
                        mask, _ = appliance_foreground_mask(secondary_world, mask, self.work_surface_measurement,
                                                            crop_to_support=self.appliance_support_crop_v5)
                        if any(same_segmented_instance(mask, previous) for previous in masks):
                            continue
                    if name in ("moka pot", "ramekin"):
                        for other_name, other_mask in secondary_masks.items():
                            if name == "ramekin" or other_name == "frypan":
                                mask = mask & ~other_mask
                    points = measured_points(secondary_world, mask)
                    if len(points) < 10:
                        continue
                    lo, hi = np.quantile(points, (.02, .98), axis=0)
                    if float(item.get("score", 0)) < .5 and name not in ("cabinet", "table", "microwave", "stove", "drawer", "rack", "basket", "caddy"):
                        if np.max(hi - lo) > .45 or np.min(hi - lo) <= 0:
                            continue
                    secondary.append((points, float(item.get("score", 0))))
                    masks.append(mask)
                if masks:
                    secondary_masks[name] = np.logical_or.reduce(masks)
            measured = []
            measured_evidence = {}
            measured_clouds = {}
            used_secondary = set()
            for item in reply["instances"]:
                mask = Sam3Client._decode_result(item).mask
                if mask is None or mask.shape != world.shape[:2]:
                    raise ValueError("SAM/depth image dimensions differ")
                if name == "ramekin":
                    # A ramekin mask can include its overlying bowl or a nearby
                    # package. Preserve separately detected visible surfaces.
                    original_area = np.count_nonzero(mask)
                    for other_mask in category_masks.values():
                        mask = mask & ~other_mask
                    # Near-identical bowl masks leave a thin noisy boundary;
                    # the fixed RGB ramekin body occupies about a quarter of
                    # its combined mask and survives this check.
                    if np.count_nonzero(mask) < 0.15 * original_area:
                        continue
                if name == "moka pot" and "frypan" in category_masks:
                    original_area = np.count_nonzero(mask)
                    mask = mask & ~category_masks["frypan"]
                    if np.count_nonzero(mask) < 0.15 * original_area:
                        continue
                points = world[mask].astype(np.float64)
                points = points[
                    np.isfinite(points).all(axis=1)
                    & (np.abs(points).sum(axis=1) > 1e-6)
                ]
                if len(points) < 10:
                    continue
                evidence = {"source_cameras": [camera], "fusion_version": "none",
                            "shape_fit_version": "none"}
                if self.microwave_instance_geometry_v4 and name == "microwave":
                    from robots.libero.v5_perception_geometry import appliance_foreground_mask
                    mask, filtered = appliance_foreground_mask(world, mask, self.work_surface_measurement,
                                                               crop_to_support=self.appliance_support_crop_v5)
                    points = world[mask].astype(np.float64)
                    evidence["foreground_filter"] = filtered
                    if len(points) < 30:
                        self.rejected_fixture_measurements.append({
                            "category": name, "query": item.get("geometry_query", prompt),
                            "reason": "appliance_has_no_depth_above_measured_support", **filtered})
                        continue
                if item.get("guidance"):
                    evidence["guidance"] = item["guidance"]
                joined_mask = None
                if self.dual_view_fusion_v1:
                    from robots.libero.v5_perception_geometry import fuse_cloud
                    eligible = [(p, s) for i, (p, s) in enumerate(secondary) if i not in used_secondary]
                    mapping = [i for i in range(len(secondary)) if i not in used_secondary]
                    points, joined, detail = fuse_cloud(
                        points, eligible, trim_depth_tails=self.fusion_depth_trim_v2)
                    evidence.update(fusion_version="rgbd_dual_view/1", fusion=detail)
                    if joined is not None:
                        used_secondary.add(mapping[joined])
                        evidence["source_cameras"].append(secondary_camera)
                        joined_mask = masks[mapping[joined]]
                lower, upper = np.quantile(points, (0.02, 0.98), axis=0)
                centre = np.median(points, axis=0)
                if self.shape_fit_v1:
                    from robots.libero.v5_perception_geometry import fit_shape
                    centre, lower, upper, fitted = fit_shape(points, name)
                    evidence.update(shape_fit_version="measured_shape/1", shape=fitted)
                if self.shape_completion_v2:
                    from robots.libero.v5_perception_geometry import complete_shape_height
                    centre, lower, upper, completion = complete_shape_height(points, name, centre, lower, upper)
                    evidence["shape_completion"] = completion
                score = float(item.get("score", 0.0))
                if self.microwave_recall_geometry_v3 and name == "microwave":
                    from robots.libero.v5_perception_geometry import microwave_geometry_supported
                    if not microwave_geometry_supported(lower, upper, self.work_surface_measurement,
                                                         require_support_contact=self.appliance_support_crop_v5):
                        self.rejected_fixture_measurements.append({
                            "category": name, "lower": lower.tolist(), "upper": upper.tolist(),
                            "score": score, "query": item.get("geometry_query", prompt),
                            "reason": "microwave_shape_or_measured_support_region_mismatch"})
                        continue
                    evidence.update(geometry_query=item.get("geometry_query", prompt),
                                    work_surface=self.work_surface_measurement)
                if self.instruction_queries_v1 and score < .5 and name not in (
                    "cabinet", "table", "microwave", "stove", "drawer", "rack", "basket", "caddy"):
                    # A low-confidence whole-background mask is not a small
                    # graspable object. Check measured extents, not sim poses.
                    if np.max(upper - lower) > .45 or np.min(upper - lower) <= 0:
                        continue
                candidate = (tuple(centre), tuple(lower), tuple(upper), score, mask)
                if self.microwave_instance_geometry_v4 and name == "microwave":
                    from robots.libero.v5_perception_geometry import same_segmented_instance
                    if any(same_segmented_instance(mask, old_item[4]) for old_item in measured):
                        self.rejected_fixture_measurements.append({
                            "category": name, "query": item.get("geometry_query", prompt),
                            "reason": "duplicate_segmented_appliance_surface"})
                        continue
                # SAM can return nested/duplicate masks for one package. Keep
                # one measured instance per nearby physical centre.
                if any(math.dist(candidate[0], old_item[0]) <= 0.02 for old_item in measured):
                    continue
                measured.append(candidate)
                if self.record_sam_masks_v6:
                    evidence["sam_mask_files"] = {camera: self.save_sam_mask(mask, camera)}
                    if joined_mask is not None:
                        evidence["sam_mask_files"][secondary_camera] = self.save_sam_mask(joined_mask, secondary_camera)
                measured_evidence[candidate[0]] = evidence
                measured_clouds[candidate[0]] = points
            if not measured and self.dual_view_fusion_v1:
                # Recall from the second camera must still be a measured,
                # geometrically checked instance, not an invented parent pose.
                for secondary_index, (points, score) in enumerate(secondary):
                    lower, upper = np.quantile(points, (.02, .98), axis=0)
                    centre = np.median(points, axis=0)
                    if self.microwave_recall_geometry_v3 and name == "microwave":
                        from robots.libero.v5_perception_geometry import microwave_geometry_supported
                        if not microwave_geometry_supported(lower, upper, self.work_surface_measurement,
                                                             require_support_contact=self.appliance_support_crop_v5):
                            continue
                    evidence = {"source_cameras": [secondary_camera], "fusion_version": "rgbd_dual_view/1",
                                "fusion": {"fused": False, "primary_missing": True}, "shape_fit_version": "none"}
                    if self.shape_fit_v1:
                        from robots.libero.v5_perception_geometry import fit_shape
                        centre, lower, upper, fitted = fit_shape(points, name)
                        evidence.update(shape_fit_version="measured_shape/1", shape=fitted)
                    if self.shape_completion_v2:
                        from robots.libero.v5_perception_geometry import complete_shape_height
                        centre, lower, upper, completion = complete_shape_height(points, name, centre, lower, upper)
                        evidence["shape_completion"] = completion
                    mask = np.zeros(world.shape[:2], dtype=bool)
                    item = (tuple(centre), tuple(lower), tuple(upper), score, mask)
                    if any(math.dist(item[0], old_item[0]) <= .02 for old_item in measured):
                        continue
                    measured.append(item)
                    if self.record_sam_masks_v6:
                        evidence["sam_mask_files"] = {secondary_camera: self.save_sam_mask(masks[secondary_index], secondary_camera)}
                    measured_evidence[item[0]] = evidence
                    measured_clouds[item[0]] = points
            if placement:
                placed, target = placement
                measured = [item for item in measured if target.visible and all(
                    target.lower[i] <= item[0][i] <= target.upper[i] for i in (0, 1)
                )]
                if len(measured) != 1:
                    measured = []
            limit = self.instance_limits.get(name)
            if limit is not None:
                # LIBERO supplies scene object names to both RPent and v5.
                # A second generic package mask must not overwrite another
                # category when only one instance of this category is listed.
                measured = sorted(measured, key=lambda item: item[3], reverse=True)[:limit]
            if measured:
                category_masks[name] = np.logical_or.reduce([item[4] for item in measured])
            old = [e for e in self.entities.values() if e.name == name
                   and (placement is None or e.id == placed.id)]
            if self.fixture_identity_cache_v1:
                old += [e for e in self._rejected_fixture_entities.values() if e.name == name]
            # Associate by measurements, never by simulator object poses/IDs.
            pairs = sorted(
                (math.dist(e.xyz, m[0]), e.id, index)
                for e in old
                for index, m in enumerate(measured)
            )
            matched_old, matched_new = set(), set()
            for _, eid, index in pairs:
                if eid in matched_old or index in matched_new:
                    continue
                xyz, lower, upper, score, mask = measured[index]
                self.entities[eid] = Entity(
                    eid, name, xyz, lower, upper, source_step=state.latest_step,
                    geometry="shape_prior_height" if measured_evidence[xyz].get("shape_completion", {}).get("accepted") else None,
                )
                self._scores[eid] = score
                self.perception_evidence[eid] = measured_evidence[xyz]
                self.measurement_clouds[eid] = measured_clouds[xyz]
                self._rejected_fixture_entities.pop(eid, None)
                instance_masks[eid] = mask
                matched_old.add(eid)
                matched_new.add(index)
            for e in old:
                if e.id not in matched_old and e.id in self.entities:
                    cache = self.occluded_measurement_cache_v2 and not fixture_actions(e.name) and not e.part_of
                    self.entities[e.id] = replace(e, visible=False, geometry=(
                        "cached_perception_" + (e.geometry or "visible_surface").removeprefix("cached_perception_")
                        if cache else e.geometry))
            for index, (xyz, lower, upper, score, mask) in enumerate(measured):
                if index not in matched_new:
                    near = [
                        e for e in self.entities.values()
                        if np.count_nonzero(mask) > 0
                        if e.visible
                        and math.dist(e.xyz, xyz) <= 0.02
                        and e.id in instance_masks
                        and np.count_nonzero(mask & instance_masks[e.id])
                        >= 0.7 * np.count_nonzero(mask | instance_masks[e.id])
                        and all(
                            min(e.upper[i], upper[i]) - max(e.lower[i], lower[i]) > 0
                            for i in (0, 1)
                        )
                    ]
                    if near:
                        existing = min(near, key=lambda e: math.dist(e.xyz, xyz))
                        if score <= self._scores.get(existing.id, 0.0):
                            continue
                        self.entities[existing.id] = Entity(
                            existing.id, name, xyz, lower, upper,
                            source_step=state.latest_step,
                            geometry="shape_prior_height" if measured_evidence[xyz].get("shape_completion", {}).get("accepted") else None,
                        )
                        self._scores[existing.id] = score
                        self.perception_evidence[existing.id] = measured_evidence[xyz]
                        self.measurement_clouds[existing.id] = measured_clouds[xyz]
                        instance_masks[existing.id] = mask
                        continue
                    if not self._ids:
                        raise ValueError("episode exhausted neutral ID pool")
                    eid = self._ids.pop()
                    self.entities[eid] = Entity(
                        eid, name, xyz, lower, upper, source_step=state.latest_step,
                        geometry="shape_prior_height" if measured_evidence[xyz].get("shape_completion", {}).get("accepted") else None,
                    )
                    self._scores[eid] = score
                    self.perception_evidence[eid] = measured_evidence[xyz]
                    self.measurement_clouds[eid] = measured_clouds[xyz]
                    instance_masks[eid] = mask
            self.last_measurement_s[name] = time.perf_counter()
        if self.fixture_support_filter_v1:
            from robots.libero.v5_fixture_parts import above_work_surface
            if self.support_z is None:
                supports = [e.lower[2] for e in self.entities.values() if e.visible
                            and not e.part_of and not e.name.startswith("area ")
                            and e.name not in ("cabinet", "microwave", "stove", "drawer", "rack", "basket", "caddy")]
                if supports:
                    self.support_z = float(np.median(supports))
            for e in list(self.entities.values()):
                if e.name in ("cabinet", "microwave", "stove", "drawer") and not above_work_surface(e, self.support_z):
                    self.rejected_fixture_measurements.append({
                        "measurement": entity_record(e), "support_z": self.support_z,
                        "reason": "entire_detection_below_measured_work_surface"})
                    self.entities.pop(e.id)
                    if self.fixture_identity_cache_v1:
                        # Keep only a private geometric association for rejected
                        # background masks. They remain absent from public state;
                        # reobserving one must not consume another neutral ID.
                        self._rejected_fixture_entities[e.id] = e
                    instance_masks.pop(e.id, None)
                    for part in list(self.entities.values()):
                        if part.part_of == e.id:
                            self.entities.pop(part.id)
        if self.furniture_parts_v1:
            self.refresh_fixture_parts(world, instance_masks, camera, refreshed_names=names)
        self.refresh_instruction_regions()
        self.perception_s += time.perf_counter() - started
        if self.wrist_recall_v1 and camera == "agentview" and placement is None:
            missing = [name for name in names if not any(e.visible and e.name == name for e in self.entities.values())]
            if missing:
                self.refresh(missing, camera_view="wrist")

    def save_sam_mask(self, mask: np.ndarray, camera: str) -> dict:
        """Persist the actual per-instance mask used for measured geometry."""
        from pathlib import Path
        state = self.toolkit._state
        name = f"v6_sam_{camera}_{hashlib.sha256(mask.tobytes()).hexdigest()[:16]}.npz"
        if state.save(name, mask, step=state.latest_step) is None:
            raise RuntimeError("could not persist v6 measured-entity SAM mask")
        path = Path(state.artifact_path(name, step=state.latest_step))
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "camera": camera, "source_step": state.latest_step,
                "source": "SAM_instance_used_for_measurement"}

    def refresh_fixture_parts(self, world, instance_masks, camera="agentview", *, refreshed_names=()) -> None:
        """Keep part IDs stable and derive only bands with current depth points."""
        from robots.libero.v5_fixture_parts import associated_drawers, fixture_parts, fixture_points, infer_cabinet_front, measured_handle_front
        from robots.libero.v5_state import entity_record

        cabinets = [e for e in self.entities.values() if e.name == "cabinet" and e.visible]
        drawers = [e for e in self.entities.values()
                   if e.name == "drawer" and e.visible and e.id in instance_masks]
        for parent in list(self.entities.values()):
            if (self.fixture_part_visibility_v2 and parent.name in refreshed_names
                    and not parent.visible):
                # A failed fresh parent detection cannot leave its old derived
                # door/drawer advertised as currently visible. Keep measured
                # coordinates and IDs for association; placement caches belong
                # to the executor and do not depend on public visibility.
                for part in list(self.entities.values()):
                    if part.part_of == parent.id:
                        self.entities[part.id] = replace(part, visible=False)
            attached = (associated_drawers(parent, cabinets, drawers)
                        if self.fixture_drawer_clouds_v2 and parent.name == "cabinet" else [])
            if parent.name not in ("cabinet", "microwave", "stove") or (
                parent.id not in instance_masks and not attached
            ):
                continue
            for part in list(self.entities.values()):
                if part.part_of == parent.id:
                    self.entities[part.id] = replace(part, visible=False)
            if parent.id in instance_masks:
                from robots.libero.v5_perception_geometry import measured_points

                points = (self.measurement_clouds[parent.id] if parent.id in self.measurement_clouds
                          else measured_points(world, instance_masks[parent.id]))
                selection = "segmented_instance_clouds_rgbd/2-dev"
            else:
                # Only an independently segmented open drawer can refresh a
                # currently occluded cabinet. Retain the explicit cached-bound
                # provenance for its static support, rather than calling it a
                # current instance mask.
                points = fixture_points(world, parent)
                selection = "cached_cabinet_bounds_current_rgbd/1"
            if attached:
                # All added clouds were segmented in this capture. A cached
                # cabinet bound can select its static body in the current RGB-D
                # frame; cached moving-drawer clouds must never be reused.
                points = np.concatenate([points, *[self.measurement_clouds[e.id] for e in attached]])
            handle_axis, handle_evidence = None, None
            if (self.fixture_handle_geometry_v3 and parent.name == "cabinet"
                    and parent.id in instance_masks):
                handle_axis, handle_evidence, handle_points = measured_handle_front(world, parent)
                if handle_axis is not None:
                    points = np.concatenate([points, handle_points])
            state = self.toolkit._state
            source_step = state.latest_step if attached else parent.source_step
            # Branch restore can revisit a recorded step with different pixels.
            # Keep each measurement immutable instead of overwriting its ledger.
            cloud_id = hashlib.sha256(np.ascontiguousarray(points).tobytes()).hexdigest()[:16]
            name = f"fixture_points_{parent.id}_{camera}_{cloud_id}.npz"
            if state.save(name, points, step=source_step) is None:
                raise RuntimeError("could not persist measured fixture points")
            path = state.artifact_path(name, step=source_step)
            self.fixture_measurement_evidence[parent.id] = {
                "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "parent": entity_record(parent), "camera": camera,
                "source_step": source_step, "point_selection": selection}
            if attached:
                self.fixture_measurement_evidence[parent.id].update(
                    point_selection="current_cabinet_instance_plus_current_drawer_masks_rgbd/3-dev"
                    if parent.id in instance_masks else "cabinet_bounds_plus_current_drawer_masks_rgbd/2-dev",
                    parent_cloud_selection=selection,
                    separately_segmented_drawers=[entity_record(e) for e in attached],
                    cabinet_bound_source_step=parent.source_step,
                )
            front = self.view_axes[1]
            if self.fixture_front_geometry_v1 and parent.name == "cabinet":
                meta = self.toolkit._state.load(f"{camera}_metadata.json")
                camera_xyz = np.asarray(meta["extrinsic_cam2world"], dtype=float)[:3,3]
                front, calibration = infer_cabinet_front(points, camera_xyz, self.fixture_front_axes.get(parent.id))
                if front is None and handle_axis is not None:
                    front, calibration = handle_axis, handle_evidence
                self.fixture_measurement_evidence[parent.id]["front_calibration"] = calibration
                self.fixture_measurement_evidence[parent.id]["fixture_front_axis"] = front
                if front is not None:
                    self.fixture_front_axes[parent.id] = front
            if self.microwave_door_cloud_v6 and parent.name == "microwave":
                parts = self._measure_microwave_door(parent, camera)
            else:
                parts = fixture_parts(parent, points, front, calibrated_front=self.fixture_front_geometry_v1)
            for measured in parts:
                old = next((e for e in self.entities.values()
                            if e.name == measured["name"] and e.part_of == parent.id), None)
                eid = old.id if old else self._ids.pop()
                self.entities[eid] = Entity(eid, **measured, part_of=parent.id,
                                            source_step=source_step)

    def _measure_microwave_door(self, parent: Entity, camera: str) -> list[dict]:
        """Use a distinct door mask; a shell cloud does not measure its door."""
        from robots.libero.v5_fixture_parts import measured_microwave_door
        from robots.libero.v5_perception_geometry import appliance_foreground_mask, measured_points
        from rpent.robots.components.sam3_client import Sam3Client

        state = self.toolkit._state
        started = time.perf_counter()
        query = "door of the microwave"
        cameras = [camera]
        if self.dual_view_fusion_v1:
            cameras.append("wrist" if camera == "agentview" else "agentview")
        views, diagnostics = {}, []
        for view in cameras:
            image = base64.b64encode(state.load_bytes(f"{view}_high.png")).decode("ascii")
            world = state.load(f"{view}_world_high.npz")
            reply = self.rpc.call("sam3.segment_all", kwargs={"image_base64": image,
                "text_prompt": query, "min_score": .5}, timeout_s=120)
            self.calls += 1
            if self.door_point_recall_v7 and not reply.get("instances"):
                from robots.libero.v5_fixture_parts import adjacent_panel_prompt

                point, guidance = adjacent_panel_prompt(world, parent)
                diagnostics.append({"camera": view, "guidance": guidance})
                if point is not None:
                    guided = self.rpc.call("sam3.segment", kwargs={"image_base64": image,
                        "point": point, "min_score": .5}, timeout_s=120)
                    self.calls += 1
                    if guided.get("found"):
                        reply = {"instances": [{**guided, "guidance": guidance}]}
            measurements = []
            for item in reply.get("instances", []):
                mask = Sam3Client._decode_result(item).mask
                if mask is None or mask.shape != world.shape[:2]:
                    continue
                mask, filtering = appliance_foreground_mask(world, mask, self.work_surface_measurement)
                cloud = measured_points(world, mask)
                if self.door_plane_consensus_v1:
                    from robots.libero.v5_verification import moving_panel_points

                    cloud, panel = moving_panel_points(cloud, self._microwave_frame_anchors.get((parent.id, view)))
                    filtering = {**filtering, "panel": panel}
                measured, evidence = measured_microwave_door(parent, cloud)
                diagnostics.append({"camera": view, "score": item.get("score"),
                                    "guidance": item.get("guidance"), "filtering": filtering, **evidence})
                if measured is not None:
                    measurements.append((measured, cloud))
            views[view] = measurements
        evidence = {"query": query, "source_step": state.latest_step,
                    "source": "perception", "accepted_instances": sum(map(len, views.values())),
                    "accepted_by_camera": {view: len(items) for view, items in views.items()},
                    "instances": diagnostics}
        self.fixture_measurement_evidence[parent.id]["door_measurement"] = evidence
        self.perception_s += time.perf_counter() - started
        if any(len(items) > 1 for items in views.values()):
            evidence["reason"] = "ambiguous_door_instances"
            return []
        visible = [(view, items[0]) for view, items in views.items() if items]
        if not visible:
            evidence["reason"] = "door_not_measured_in_available_views"
            return []
        measured, cloud = visible[0][1]
        if len(visible) == 2:
            from robots.libero.v5_perception_geometry import fuse_cloud

            combined, joined, fusion = fuse_cloud(cloud, [(visible[1][1][1], 1.)])
            measured, plane = measured_microwave_door(parent, combined) if joined is not None else (None, {})
            evidence.update(fusion=fusion, fused_plane=plane)
            if measured is None:
                evidence["reason"] = "door_views_not_one_adjacent_plane"
                return []
            cloud = combined
        evidence["source_cameras"] = [view for view, _ in visible]
        identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
        filename = f"microwave_door_{parent.id}_{camera}_{identity}.npz"
        if state.save(filename, cloud, step=state.latest_step) is None:
            raise RuntimeError("could not persist measured microwave door cloud")
        path = state.artifact_path(filename, step=state.latest_step)
        evidence.update(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return [measured]

    def refresh_instruction_regions(self) -> None:
        """Derive a table destination from measured anchor bounds and support height."""
        for eid, entity in self.entities.items():
            if entity.name.startswith("area "):
                self.entities[eid] = replace(entity, visible=False)
        visible = [e for e in self.entities.values() if e.visible and not e.name.startswith("area ")]
        support = [e.lower[2] for e in visible if not any(
            word in e.name for word in ("cabinet", "drawer", "microwave", "stove", "rack")
        )]
        if not support:
            return
        for direction, anchor_kind in instruction_regions(self.instruction):
            anchors = [e for e in visible if e.name == anchor_kind]
            if len(anchors) != 1:
                continue
            anchor = anchors[0]
            if getattr(self, "region_anchor_cache_v1", False):
                # Placing an object on the anchor hides part of its surface.
                # Keep the destination's pre-contact measurement until an
                # action explicitly moves the anchor itself.
                anchor = self.region_anchors.setdefault(anchor.id, anchor)
            axis = np.asarray(self.view_axes[0 if direction in ("left", "right") else 1])
            if direction in ("left", "back"):
                axis = -axis
            half_width = sum(abs(axis[i]) * (anchor.upper[i] - anchor.lower[i]) / 2 for i in (0, 1))
            xyz = np.asarray(anchor.xyz) + axis * (half_width + 0.06)
            xyz[2] = min(support)
            name = region_name(direction, anchor_kind)
            old = next((e for e in self.entities.values() if e.name == name), None)
            eid = old.id if old is not None else self._ids.pop()
            lower, upper = xyz - (0.04, 0.04, 0), xyz + (0.04, 0.04, 0)
            self.entities[eid] = Entity(eid, name, tuple(xyz), tuple(lower), tuple(upper), source_step=anchor.source_step)

    def measure_handle(self, obj: Entity) -> tuple | None:
        """Query a handle on the current camera frame and reject remote masks."""
        started = time.perf_counter()
        state = self.toolkit._state
        image = base64.b64encode(state.load_bytes("agentview_high.png")).decode("ascii")
        world = state.load("agentview_world_high.npz")
        reply = self.rpc.call("sam3.segment_all", kwargs={"image_base64": image,
                              "text_prompt": f"handle of the {obj.name}", "min_score": .35}, timeout_s=120)
        self.calls += 1
        centres = []
        for item in reply.get("instances", []):
            mask = Sam3Client._decode_result(item).mask
            if mask is None or mask.shape != world.shape[:2]:
                continue
            cloud = world[mask]
            cloud = cloud[np.isfinite(cloud).all(axis=1) & (np.abs(cloud).sum(axis=1) > 1e-6)]
            if len(cloud) < 10:
                continue
            centre = np.median(cloud, axis=0)
            if all(obj.lower[i] - .04 <= centre[i] <= obj.upper[i] + .04 for i in range(3)):
                centres.append(tuple(float(x) for x in centre))
        self.perception_s += time.perf_counter() - started
        return centres[0] if len(centres) == 1 else None

    def measure_fixture_endpoint(self, parent: Entity, moving_phrase: str, *, camera_view="agentview") -> dict:
        """Measure distinct moving and fixed faces from RGB-D, never sim joints."""
        from robots.libero.v5_perception_geometry import measured_points
        from robots.libero.v5_verification import vertical_face
        state = self.toolkit._state
        started = time.perf_counter()
        image = base64.b64encode(state.load_bytes(f"{camera_view}_high.png")).decode("ascii")
        world = state.load(f"{camera_view}_world_high.npz")
        geometry_evidence = None
        if getattr(self, "fixture_endpoint_geometry_v3", False) and parent.name == "cabinet":
            from robots.libero.v5_fixture_parts import measured_drawer_faces
            label = re.search(r"\b(top|upper|middle|bottom|lower) drawer\b", moving_phrase)
            name = {"upper": "top", "lower": "bottom"}.get(label[1], label[1]) if label else None
            parts = [e for e in self.entities.values() if e.part_of == parent.id
                     and e.name == f"cabinet {name} drawer" and e.visible]
            key = (parent.id, name)
            if key not in self._drawer_endpoint_anchors and len(parts) == 1:
                self._drawer_endpoint_anchors[key] = (parent, parts[0])
            anchors = self._drawer_endpoint_anchors.get(key)
            if anchors is not None:
                evidence, clouds = measured_drawer_faces(world, *anchors, self.fixture_front_axes.get(parent.id))
                geometry_evidence = evidence
                if evidence.get("frame") and evidence.get("moving"):
                    for kind, cloud in clouds.items():
                        identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
                        filename = f"articulation_{parent.id}_{kind}_geometry3_{identity}.npz"
                        if state.save(filename, cloud, step=state.latest_step) is None:
                            raise RuntimeError("could not persist measured articulation cloud")
                        path = state.artifact_path(filename, step=state.latest_step)
                        evidence[kind].update(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    self.perception_s += time.perf_counter() - started
                    return {**evidence, "source_step": state.latest_step, "source": "perception"}
        frame = "front frame around the microwave door" if "microwave" in parent.name else "cabinet frame around the drawers"
        result = {"source_step": state.latest_step, "source": "perception", "measurement_counts": {}}
        microwave_geometry = (getattr(self, "fixture_endpoint_geometry_v3", False)
                              and parent.name == "microwave")
        if microwave_geometry:
            # Use the same query and measured point recall as the part detector.
            # A frame query can also segment the open door; that mask is not
            # an independent fixed reference merely because the text says frame.
            moving_phrase = "door of the microwave"
        accepted_masks = {}
        if geometry_evidence is not None:
            result["geometry_fallback_evidence"] = geometry_evidence
        for key, phrase in (("frame", frame), ("moving", moving_phrase)):
            reply = self.rpc.call("sam3.segment_all", kwargs={"image_base64": image,
                                  "text_prompt": phrase, "min_score": .5}, timeout_s=120)
            self.calls += 1
            guidance = None
            if (microwave_geometry and key == "moving" and self.door_point_recall_v7
                    and not reply.get("instances")):
                from robots.libero.v5_fixture_parts import adjacent_panel_prompt

                point, guidance = adjacent_panel_prompt(world, parent)
                if point is not None:
                    guided = self.rpc.call("sam3.segment", kwargs={"image_base64": image,
                        "point": point, "min_score": .5}, timeout_s=120)
                    self.calls += 1
                    if guided.get("found"):
                        reply = {"instances": [guided]}
            fits = []
            masks = []
            counts = {"query": phrase, "sam_instances": len(reply.get("instances", [])),
                      "invalid_mask": 0, "insufficient_depth": 0, "outside_parent": 0,
                      "nonplanar": 0, "accepted_faces": 0}
            if guidance is not None:
                counts["point_guidance"] = guidance
            for item in reply.get("instances", []):
                mask = Sam3Client._decode_result(item).mask
                if mask is None or mask.shape != world.shape[:2]:
                    counts["invalid_mask"] += 1
                    continue
                if microwave_geometry and key == "moving":
                    from robots.libero.v5_perception_geometry import appliance_foreground_mask

                    mask, filtering = appliance_foreground_mask(world, mask, self.work_surface_measurement)
                    counts.setdefault("foreground_filters", []).append(filtering)
                cloud = measured_points(world, mask)
                if microwave_geometry and key == "moving" and self.door_plane_consensus_v1:
                    from robots.libero.v5_verification import moving_panel_points

                    cloud, panel = moving_panel_points(
                        cloud, self._microwave_frame_anchors.get((parent.id, camera_view)))
                    counts.setdefault("panel_filters", []).append(panel)
                if len(cloud) < 30:
                    counts["insufficient_depth"] += 1
                    continue
                centre = np.median(cloud, axis=0)
                margin = .01 if microwave_geometry and key == "frame" else .15
                if not all(parent.lower[i] - margin <= centre[i] <= parent.upper[i] + margin for i in range(3)):
                    counts["outside_parent"] += 1
                    continue
                if microwave_geometry and key == "frame":
                    # A fixed frame must be measured inside the segmented shell,
                    # not a neighbouring moving panel outside that shell.
                    inside = ((cloud >= np.asarray(parent.lower) - margin)
                              & (cloud <= np.asarray(parent.upper) + margin)).all(axis=1)
                    if np.mean(inside) < .95:
                        counts["outside_parent"] += 1
                        continue
                face = vertical_face(cloud)
                if face is None:
                    counts["nonplanar"] += 1
                    continue
                identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
                name = f"articulation_{parent.id}_{key}_{camera_view}_{identity}.npz"
                if state.save(name, cloud, step=state.latest_step) is None:
                    raise RuntimeError("could not persist measured articulation cloud")
                path = state.artifact_path(name, step=state.latest_step)
                fits.append({**face, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                masks.append(mask)
            counts["accepted_faces"] = len(fits)
            result["measurement_counts"][key] = counts
            result[key] = fits[0] if len(fits) == 1 else None
            accepted_masks[key] = masks[0] if len(masks) == 1 else None
        if microwave_geometry and all(accepted_masks.get(key) is not None for key in ("frame", "moving")):
            intersection = np.count_nonzero(accepted_masks["frame"] & accepted_masks["moving"])
            overlap = intersection / min(np.count_nonzero(accepted_masks[key]) for key in ("frame", "moving"))
            result["frame_moving_mask_overlap"] = overlap
            if overlap > .05:
                result["frame"] = None
                result["reason"] = "fixed_and_moving_faces_not_independent"
        if microwave_geometry and result["frame"] is None:
            from robots.libero.v5_fixture_parts import measured_microwave_frame

            camera = np.asarray(state.load(f"{camera_view}_metadata.json")["extrinsic_cam2world"])[:3, 3]
            key = (parent.id, camera_view)
            frame, evidence, cloud, anchor = measured_microwave_frame(
                world, parent, camera, accepted_masks.get("moving"), result["moving"],
                self._microwave_frame_anchors.get(key))
            result["fixed_frame_geometry"] = evidence
            if anchor is not None:
                self._microwave_frame_anchors[key] = anchor
            if frame is not None:
                identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
                name = f"articulation_{parent.id}_frame_{camera_view}_geometry8_{identity}.npz"
                if state.save(name, cloud, step=state.latest_step) is None:
                    raise RuntimeError("could not persist measured fixed frame cloud")
                path = state.artifact_path(name, step=state.latest_step)
                result["frame"] = {**frame, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.perception_s += time.perf_counter() - started
        if microwave_geometry and self.dual_view_fusion_v1 and camera_view == "agentview":
            secondary = self.measure_fixture_endpoint(parent, moving_phrase, camera_view="wrist")
            result["views"] = {"agentview": dict(result), "wrist": secondary}
            for key in ("frame", "moving"):
                measured = [(view, sample[key]) for view, sample in result["views"].items() if sample.get(key)]
                result[key] = measured[0][1] if len(measured) == 1 else None
                if len(measured) == 2:
                    clouds = []
                    for _, face in measured:
                        with np.load(face["path"]) as data:
                            clouds.append(data[data.files[0]])
                    cloud = np.concatenate(clouds)
                    fit = vertical_face(cloud)
                    if fit is not None:
                        identity = hashlib.sha256(np.ascontiguousarray(cloud).tobytes()).hexdigest()[:16]
                        name = f"articulation_{parent.id}_{key}_dual_{identity}.npz"
                        if state.save(name, cloud, step=state.latest_step) is None:
                            raise RuntimeError("could not persist fused articulation cloud")
                        path = state.artifact_path(name, step=state.latest_step)
                        result[key] = {**fit, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                if result[key] is not None:
                    result[key] = {**result[key], "source_cameras": [view for view, _ in measured]}
        return result


class V5Executor:
    """Run finite skills and verify them with measured visual receipts."""

    def __init__(
        self,
        toolkit,
        scene: MeasuredScene,
        max_chunks: int = 40,
        instruction: str = "",
        *,
        target_cache_v1: bool = False,
        strict_place_v1: bool = False,
        strict_place_v2: bool = False,
        strict_place_v3: bool = False,
        strict_place_v4: bool = False,
        strict_place_v5: bool = False,
        adjust_place_v1: bool = False,
        articulate_verification_v1: bool = False,
        grasp_approach_v1: bool = False,
        grasp_retry_v1: bool = False,
        grasp_local_prompt_v1: bool = False,
        grasp_short_prompt_v2: bool = False,
        in_release_clearance_v1: bool = False,
        selected_fixture_target_v1: bool = False,
        wrist_refine_v1: bool = False,
        wrist_measurement_standoff_v2: bool = False,
        wrist_geometry_prompt_v3: bool = False,
        grasp_rim_v1: bool = False,
        measured_rim_v2: bool = False,
        mug_rim_first_v3: bool = False,
        handle_free_yaw_v2: bool = False,
        grasp_lift_check_v2: bool = False,
        grasp_occlusion_scan_v1: bool = False,
        native_grasp_stop_v1: bool = False,
        view_retreat_v2: bool = False,
        retreat_clearance_v1: bool = False,
        articulate_verification_v2: bool = False,
        fixture_in_contact_v1: bool = False,
        grasp_clearance_v1: bool = False,
        fixture_part_prompt_v1: bool = False,
        articulate_view_retreat_v1: bool = False,
        held_occlusion_v1: bool = False,
        motion_outcome_v1: bool = False,
        motion_trace_v1: bool = False,
        grasp_safe_approach_v2: bool = False,
        wrist_position_hold_v1: bool = False,
        stagnation_recovery_v1: bool = False,
        skill_profiles: dict | None = None,
    ) -> None:
        self.toolkit = toolkit
        self.p = toolkit.primitives
        self.scene = scene
        self.held: str | None = None
        self.held_offset: np.ndarray | None = None
        self.receipts: list[dict] = []
        self.max_chunks = max_chunks
        self.instruction = instruction
        self.target_cache_v1 = target_cache_v1
        self.strict_place_v1 = strict_place_v1
        self.strict_place_v2 = strict_place_v2
        self.strict_place_v3 = strict_place_v3
        self.strict_place_v4 = strict_place_v4
        self.strict_place_v5 = strict_place_v5
        self.adjust_place_v1 = adjust_place_v1
        self.articulate_verification_v1 = articulate_verification_v1
        self.grasp_approach_v1 = grasp_approach_v1
        self.grasp_retry_v1 = grasp_retry_v1
        self.grasp_local_prompt_v1 = grasp_local_prompt_v1
        self.grasp_short_prompt_v2 = grasp_short_prompt_v2
        self.in_release_clearance_v1 = in_release_clearance_v1
        self.selected_fixture_target_v1 = selected_fixture_target_v1
        self.wrist_refine_v1 = wrist_refine_v1
        self.wrist_measurement_standoff_v2 = wrist_measurement_standoff_v2
        self.wrist_geometry_prompt_v3 = wrist_geometry_prompt_v3
        self.grasp_rim_v1 = grasp_rim_v1
        self.measured_rim_v2 = measured_rim_v2
        self.mug_rim_first_v3 = mug_rim_first_v3
        self.handle_free_yaw_v2 = handle_free_yaw_v2
        self.grasp_lift_check_v2 = grasp_lift_check_v2
        self.grasp_occlusion_scan_v1 = grasp_occlusion_scan_v1
        self._grasp_occlusion_scan_used = False
        self.native_grasp_stop_v1 = native_grasp_stop_v1
        self.view_retreat_v2 = view_retreat_v2
        self.retreat_clearance_v1 = retreat_clearance_v1
        self.view_retreat_pose = self.p._last_obs_eef_pos.copy() if view_retreat_v2 else None
        self.articulate_verification_v2 = articulate_verification_v2
        self.fixture_in_contact_v1 = fixture_in_contact_v1
        self.grasp_clearance_v1 = grasp_clearance_v1
        self.fixture_part_prompt_v1 = fixture_part_prompt_v1
        self.articulate_view_retreat_v1 = articulate_view_retreat_v1
        self.held_occlusion_v1 = held_occlusion_v1
        self.motion_outcome_v1 = motion_outcome_v1
        self.motion_trace_v1 = motion_trace_v1
        self.grasp_safe_approach_v2 = grasp_safe_approach_v2
        self.wrist_position_hold_v1 = wrist_position_hold_v1
        self.stagnation_recovery_v1 = stagnation_recovery_v1
        self.recovery_view_pose = self.p._last_obs_eef_pos.copy() if stagnation_recovery_v1 else None
        self.public_recovery: dict | None = None
        self.wrist_scan_direction = 1
        self.skill_profiles = skill_profiles
        self.target_cache: dict[str, Entity] = {}
        self.last_verification_measurements: dict = {}
        self.motion_evidence: list[dict] = []
        self.last_skill_profile_evidence: dict = {}

    def capture(self, *, sync_robot: bool = False) -> None:
        # Composite skills bypass execute_tool; publish their native termination
        # through the toolkit before scoring or taking the next measurement.
        self.toolkit.get_env_state(
            command={"action": "v5_measurement"}, result={}, elapsed_s=0.0
        )
        if sync_robot:
            # A branch restore rebuilds raw sensors while preserving the
            # pre-branch observation cache. Use the captured robot sensors for
            # future image decisions, without changing the saved old request.
            measured = self.toolkit._state.latest_record().state
            observation = dict(self.p._last_obs)
            states = np.array(observation["states"], copy=True)
            states[:3] = measured["robot0_eef_pos"]
            states[6:8] = measured["robot0_gripper_qpos"]
            observation["states"] = states
            self.p.set_obs(observation)
            self.p.env.last_obs = observation

    def vla_act(
        self, prompt: str, max_chunks: int, stop: str, obj: Entity | None = None,
        *, lift_obstacle: Entity | None = None,
    ) -> dict:
        """Bound contact execution; a held-object stop requires visual evidence."""
        if stop not in ("grasp_verified", "chunk_budget", "released_object"):
            raise ValueError(f"unsupported contact stop: {stop}")
        if stop == "grasp_verified" and obj is None:
            raise ValueError("visual grasp stop requires the measured object")
        chunks = 0
        previous_opening = self.p._last_obs_gripper
        stable_chunks = 0
        verified = False
        stop_reason = "chunk_budget"
        for _ in range(max_chunks):
            if self.p.env.terminated or self.p.env.truncated:
                stop_reason = "execution_interrupted"
                break
            if self.motion_trace_v1:
                self.p._vlm_chunk(prompt, trace_callback=self.motion_evidence.append)
            else:
                self.p._vlm_chunk(prompt)
            chunks += 1
            opening = self.p._last_obs_gripper
            stable_chunks = (
                stable_chunks + 1 if abs(opening - previous_opening) <= 0.002 else 0
            )
            previous_opening = opening
            if stop == "released_object" and stable_chunks >= 2 and opening >= .075:
                stop_reason = "released_object"
                break
            lift_clear = lift_obstacle is None or not all(
                lift_obstacle.lower[i] - 0.02 <= self.p._last_obs_eef_pos[i]
                <= lift_obstacle.upper[i] + 0.02 for i in (0, 1)
            )
            if (
                stop == "grasp_verified"
                and stable_chunks >= 2
                and 0.005 <= opening <= 0.07
                and lift_clear
            ):
                if not (self.p.env.terminated or self.p.env.truncated):
                    xyz = self.p._last_obs_eef_pos.copy()
                    xyz[2] += 0.05
                    self.move(xyz, 1)
                self._refresh([obj.name])
                verified = self.verify_grasp_measurement(obj)
                if verified:
                    stop_reason = "grasp_verified"
                    break
                if self.grasp_lift_check_v2:
                    # A failed trial lift needs another approach, not repeated
                    # 5 cm increments from an increasingly distant pose.
                    stop_reason = "grasp_not_verified"
                    break
                stable_chunks = 0
        if not verified and (self.p.env.terminated or self.p.env.truncated):
            stop_reason = "execution_interrupted"
        return {
            "executed": chunks > 0,
            "chunks": chunks,
            "stop_condition": stop,
            "stop": stop_reason,
            **({"grasp_verified": verified} if stop == "grasp_verified" else {}),
            **({"object_released": stop_reason == "released_object"} if stop == "released_object" else {}),
        }

    def scan_wrist(self, names: list[str]) -> None:
        """Change the measured view while preserving the current gripper command."""
        from scipy.spatial.transform import Rotation

        q = self.p.env.raw_obs()["robot0_eef_quat"]
        rotation = Rotation.from_quat(q).as_matrix()
        yaw = math.atan2(rotation[1, 0], rotation[0, 0])
        self.motion_evidence.append(self.p.rotate_wrist(
            target_yaw=yaw + self.wrist_scan_direction * .35, gripper=0))
        self.wrist_scan_direction *= -1
        self.capture()
        self.scene.refresh(names, camera_view="wrist")

    def verify_grasp_measurement(self, before: Entity) -> bool:
        """Try one wrist view when the trial lift lost the object's measurement."""
        after = self.scene.entities.get(before.id)
        if (
            self.grasp_occlusion_scan_v1
            and not self._grasp_occlusion_scan_used
            and (after is None or not after.visible)
            and .005 <= self.p._last_obs_gripper <= .07
            and not (self.p.env.terminated or self.p.env.truncated)
        ):
            self._grasp_occlusion_scan_used = True
            self.scan_wrist([before.name])
            after = self.scene.entities.get(before.id)
            self.last_verification_measurements["grasp_occlusion_scan"] = {
                "before": entity_record(before),
                "after": entity_record(after) if after is not None else None,
                "gripper_opening": float(self.p._last_obs_gripper),
                "verified": grasp_verified(before, after, self.p._last_obs_gripper),
            }
        return grasp_verified(before, after, self.p._last_obs_gripper)

    def move(self, xyz: tuple | list, gripper: float, *, tolerance_m: float = .02,
             recoverable: bool = False) -> dict:
        """Respect the RPent planar servo range by splitting measured waypoints."""
        target = np.asarray(xyz, dtype=float)
        move_options = {}
        if self.motion_trace_v1:
            move_options.update(
                trace_steps=True,
                motion_diagnostic=lambda: self.p.env._client.call(
                    "diagnostic.motion", timeout_s=30),
            )
        if self.skill_profiles is not None:
            from robots.libero.v5_skill_profiles import parameters_for
            held = self.scene.entities.get(self.held)
            parameters = parameters_for(self.skill_profiles, held.name if held else "empty")
            move_options["step_clip"] = parameters["carry_step_clip_m"]
        for _ in range(8):
            current = self.p._last_obs_eef_pos.copy()
            distance = float(np.linalg.norm((target - current)[:2]))
            if distance <= 0.27:
                break
            mid = current + (target - current) * (0.25 / distance)
            mid[2] = max(current[2], target[2])
            result = self.p.move_to(mid.tolist(), gripper=gripper, **move_options)
            self.motion_evidence.append(
                {**result, "gripper_command": gripper, "start_eef_pos": current.tolist()}
                if self.motion_trace_v1 else result
            )
            if self.p.env.terminated or self.p.env.truncated:
                return {"executed": True, "interrupted": True}
        if self.p.env.terminated or self.p.env.truncated:
            return {"executed": False, "interrupted": True}
        start = self.p._last_obs_eef_pos.copy() if self.motion_trace_v1 else None
        result = self.p.move_to(target.tolist(), gripper=gripper, **move_options)
        self.motion_evidence.append(
            {**result, "gripper_command": gripper, "start_eef_pos": start.tolist()}
            if self.motion_trace_v1 else result
        )
        if self.motion_outcome_v1 and (self.p.env.terminated or self.p.env.truncated):
            return result
        if recoverable:
            return {**result, "waypoint_reached": result["final_dist_m"] <= tolerance_m,
                    "acceptance_distance_m": tolerance_m}
        if result["final_dist_m"] > tolerance_m:
            failure = WaypointNotReached if self.motion_outcome_v1 else RuntimeError
            raise failure(
                f"servo did not reach measured waypoint: {result['final_dist_m']} m"
            )
        return result

    def stage_grasp(self, obj: Entity, pose: list, receipt: dict) -> bool:
        """Keep the servo above the surface; the contact policy performs descent."""
        pose = list(pose)
        pose[2] = max(pose[2], obj.upper[2] + .15)
        current = self.p._last_obs_eef_pos.copy()
        height = max(float(current[2]), pose[2])
        waypoints = [[float(current[0]), float(current[1]), height],
                     [pose[0], pose[1], height], pose]
        residuals = []
        for waypoint in waypoints:
            if np.linalg.norm(np.asarray(waypoint) - self.p._last_obs_eef_pos) <= .012:
                continue
            result = self.move(waypoint, -1, tolerance_m=.08, recoverable=True)
            if self.p.env.terminated or self.p.env.truncated:
                receipt.update(executed=True, grasp_verified=False,
                               verification="failed", failure_reason="execution_interrupted")
                return False
            residuals.append(result["final_dist_m"])
            if not result["waypoint_reached"]:
                receipt.update(executed=True, grasp_verified=False, verification="failed",
                               failure_reason="approach_not_reached", recoverable=True,
                               recovery="remeasure_or_select_another_approach",
                               approach_target_xyz=pose, approach_residual_m=residuals)
                return False
        receipt.update(approach_target_xyz=pose, approach_residual_m=residuals,
                       contact_policy_standoff_m=.15, approach_acceptance_m=.08)
        return True

    def stage_wrist(self, target_yaw: float, receipt: dict) -> bool:
        """Rotate before contact while holding the measured TCP position."""
        if not self.wrist_position_hold_v1:
            rotation = self.p.rotate_wrist(target_yaw=target_yaw, gripper=-1)
            if self.motion_trace_v1:
                self.motion_evidence.append({**rotation, "gripper_command": -1})
            return True
        start = self.p._last_obs_eef_pos.copy()
        options = {}
        if self.motion_trace_v1:
            options.update(trace_steps=True, motion_diagnostic=lambda: self.p.env._client.call(
                "diagnostic.motion", timeout_s=30))
        # The loaded LIBERO OSC controllers use 0.5 rad per normalized yaw
        # command (original-task probe3292), rather than rotate_wrist's 0.1.
        rotation = self.p.move_pose(start.tolist(), target_yaw=target_yaw,
                                    rotation_action_scale=.5, gripper=-1,
                                    max_steps=150, ori_tol=.02, **options)
        evidence = {**rotation, "start_eef_pos": start.tolist(),
                    "gripper_command": -1, "rotation_action_scale": .5,
                    "wrist_position_hold_v1": True}
        self.motion_evidence.append(evidence)
        if self.p.env.terminated or self.p.env.truncated:
            receipt.update(executed=True, grasp_verified=False, verification="failed",
                           failure_reason="execution_interrupted")
            return False
        if rotation["final_dist_m"] > .02 or abs(rotation["final_yaw_err"]) > .05:
            receipt.update(executed=True, grasp_verified=False, verification="failed",
                           failure_reason="wrist_pose_not_reached", recoverable=True,
                           recovery="remeasure_or_select_another_approach",
                           wrist_position_residual_m=rotation["final_dist_m"],
                           wrist_yaw_residual_rad=rotation["final_yaw_err"])
            return False
        return True

    def retreat(self) -> None:
        if self.view_retreat_v2:
            # Repeated recovery returns to the same initially observed view
            # pose instead of accumulating 10 cm lifts outside arm reach.
            xyz = self.view_retreat_pose.copy()
        else:
            xyz = self.p._last_obs_eef_pos.copy()
            xyz[2] += 0.10
        # A missing visual verification does not mean the fingers are empty.
        # Panda's zero gripper command preserves its current actuator target;
        # only the explicit release skill should open during view recovery.
        if self.retreat_clearance_v1:
            current = self.p._last_obs_eef_pos.copy()
            height = self.fixture_transit_height(xyz, max(current[2], xyz[2]))
            # Descending diagonally from a cabinet-top placement to the view
            # pose carries the fingers through its measured front. Lift,
            # translate above the fixture, then descend at the view pose.
            if height > min(current[2], xyz[2]) + .001:
                self.move([current[0], current[1], height], 0)
                self.move([xyz[0], xyz[1], height], 0)
        self.move(xyz, 0)

    def _refresh(self, names: list[str]) -> None:
        names = [next((self.scene.entities[e.part_of].name
                       for e in self.scene.entities.values()
                       if e.name == name and e.part_of), name) for name in names]
        self.capture()
        self.scene.refresh(names)

    def grasp_approach(self, obj: Entity, action: Candidate) -> tuple[list, str, float | None]:
        """Choose a bounded staging pose from measured centre/handle geometry."""
        centre = [(lo + hi) / 2 for lo, hi in zip(obj.lower, obj.upper)]
        height = .10 if action.mode == "above_10cm" or action.tool == "regrasp_restage" else .06
        from robots.libero.v5_skill_profiles import parameters_for
        parameters = parameters_for(self.skill_profiles, obj.name)
        if parameters:
            height = parameters["restage_height_m"] if action.mode == "above_10cm" or action.tool == "regrasp_restage" else parameters["approach_height_m"]
        pose = [centre[0], centre[1], obj.upper[2] + height]
        if "rim_grasp_world_y_offset_m" in parameters:
            pose[1] += parameters["rim_grasp_world_y_offset_m"]
            return pose, "rpent_world_y_rim", None
        if self.measured_rim_v2 and any(word in obj.name for word in ("bowl", "mug", "ramekin")):
            # A symmetric container does not require a forced wrist yaw before
            # the contact policy. Select an actually observed rim patch.
            from robots.libero.v5_perception_geometry import measured_rim_point
            points = self.scene.measurement_clouds.get(obj.id)
            rim = measured_rim_point(points, self.p._last_obs_eef_pos) if points is not None else None
            if self.mug_rim_first_v3 and "mug" in obj.name and rim is not None:
                return [float(rim[0]), float(rim[1]), obj.upper[2] + height], "measured_visible_rim", None
            if "mug" in obj.name:
                handle = self.scene.measure_handle(obj)
                if handle is not None and math.dist(handle[:2], centre[:2]) >= .015:
                    return [handle[0], handle[1], obj.upper[2] + height], "measured_handle", None
            if rim is not None:
                return [float(rim[0]), float(rim[1]), obj.upper[2] + height], "measured_visible_rim", None
            return pose, "above_rim_unresolved", None
        if any(word in obj.name for word in ("mug", "moka", "frypan")):
            handle = self.scene.measure_handle(obj)
            if handle is not None and math.dist(handle[:2], centre[:2]) >= .015:
                delta = [handle[i] - centre[i] for i in (0, 1)]
                pose[:2] = handle[:2]
                return pose, "measured_handle", None if self.handle_free_yaw_v2 else math.atan2(delta[1], delta[0])
            if (self.grasp_rim_v1 or self.skill_profiles is not None) and "mug" in obj.name:
                axis = self.scene.view_axes[0]
                radius = min(obj.upper[i] - obj.lower[i] for i in (0,1)) / 2
                pose[:2] = [centre[i] + parameters.get("rim_fraction", .7) * radius * axis[i] for i in (0,1)]
                return pose, "measured_mug_rim_handle_unresolved", math.atan2(axis[1],axis[0])
            return pose, "above_handle_unresolved", None
        if (self.grasp_rim_v1 or self.skill_profiles is not None) and ("bowl" in obj.name or obj.name == "ramekin"):
            axis = self.scene.view_axes[0]
            radius = min(obj.upper[i] - obj.lower[i] for i in (0,1)) / 2
            direction = -1 if action.mode == "yaw_90" else 1
            pose[:2] = [centre[i] + direction * parameters.get("rim_fraction", .7) * radius * axis[i] for i in (0,1)]
            return pose, "measured_bowl_rim", math.atan2(axis[1],axis[0])
        if "bottle" in obj.name or obj.name in ("ketchup", "salad dressing", "barbecue sauce"):
            axis = self.scene.view_axes[1]
            direction = -1 if action.mode == "yaw_90" else 1
            pose[:2] = [centre[i] + direction * parameters.get("side_offset_m", .03) * axis[i] for i in (0, 1)]
            return pose, "measured_side", math.atan2(axis[1], axis[0])
        return pose, "measured_overhead", None

    def grasp_transit_height(self, obj: Entity, approach) -> float:
        """Clear measured fixture parts along the approach's planar segment.

        The contact policy handles descent after this staging move. A low
        diagonal move can carry the fingers through an open door before the
        end effector reaches the object.
        """
        height = max(self.p._last_obs_eef_pos[2], obj.upper[2] + .15)
        return self.fixture_transit_height(approach, height)

    def fixture_transit_height(self, destination, minimum_height) -> float:
        """Clear the visible fixture bounds along a measured planar segment."""
        start = np.asarray(self.p._last_obs_eef_pos[:2])
        delta = np.asarray(destination[:2]) - start
        height = minimum_height
        padding = max(.04, self.p._last_obs_gripper / 2) + .025
        for part in self.scene.entities.values():
            if not part.visible or not (part.part_of or part.name in ("cabinet", "microwave", "stove")):
                continue
            low, high = 0., 1.
            for i in (0, 1):
                lo, hi = part.lower[i] - padding, part.upper[i] + padding
                if abs(delta[i]) < 1e-6:
                    if not lo <= start[i] <= hi:
                        high = -1.
                        break
                else:
                    t0, t1 = sorted(((lo - start[i]) / delta[i], (hi - start[i]) / delta[i]))
                    low, high = max(low, t0), min(high, t1)
            if low <= high:
                height = max(height, part.upper[2] + .15)
        return float(height)

    def execute(self, action: Candidate, card: dict | None = None) -> dict:
        """Return a typed receipt, with no official success predicate in it."""
        receipt = {"tool": action.tool, "executed": False, "verification": "unverified"}
        self.last_verification_measurements = {}
        self._grasp_occlusion_scan_used = False
        self.motion_evidence = []
        self.last_skill_profile_evidence = {}
        for key in ("object", "target", "mode"):
            value = getattr(action, key)
            if value is not None:
                receipt[key] = value
        try:
            if self.skill_profiles is not None:
                from robots.libero.v5_skill_profiles import parameters_for
                obj = self.scene.entities.get(action.object or self.held)
                self.last_skill_profile_evidence = {"kind": self.skill_profiles["kind"],
                    "sha256": self.skill_profiles.get("sha256"),
                    "parameters": parameters_for(self.skill_profiles, obj.name if obj else "empty")}
            tool = card["selector"]["skill"] if action.tool == "card_next" and card else action.tool
            finite_skill = tool in (
                "grasp", "regrasp_restage", "place", "adjust_place", "release", "retreat"
            ) and isinstance(self.p.env, V5SkillEnvClient)
            if self.native_grasp_stop_v1 and tool in ("grasp", "regrasp_restage"):
                # A contact policy can satisfy the task before a trial lift.
                # Publish that native stop instead of lifting the object away
                # from the completed goal; placement still finishes release.
                finite_skill = False
            scope = self.p.env.complete_skill() if finite_skill else nullcontext()
            with scope:
                self._execute(action, receipt, card)
            if finite_skill:
                # The native success latch becomes visible to evaluation again
                # after the trial lift or release/retreat and visual checks.
                self.capture()
        except WaypointNotReached as error:
            # An unreachable or blocked physical waypoint is a failed skill,
            # not a Python/runtime fault. Preserve every attempted motion and
            # its distance; this does not turn failure into verified success.
            receipt.update(
                verification="failed", failure_reason="waypoint_not_reached",
                failure_detail=str(error),
                executed=any(m.get("steps_used", 0) > 0 for m in self.motion_evidence),
            )
            if action.tool in ("grasp", "regrasp_restage"):
                receipt["grasp_verified"] = False
            if action.tool in ("place", "adjust_place"):
                receipt["place_verified"] = False
            self.capture()
        except Exception as error:
            receipt.update(
                error=f"{type(error).__name__}: {error}", verification="execution_error"
            )
            if any(motion.get("steps_used", 0) > 0 for motion in self.motion_evidence):
                receipt["executed"] = True
            if action.tool in ("grasp", "regrasp_restage"):
                receipt["grasp_verified"] = False
            if action.tool in ("place", "adjust_place"):
                receipt["place_verified"] = False
            self.capture()
        self.receipts.append(receipt)
        return receipt

    def reject_terminal_action(self, action: Candidate) -> dict:
        """Keep terminal requests as receipts without ending or moving the scene."""
        if action.tool not in ("finish", "ask_help"):
            raise ValueError("only terminal requests can be rejected")
        receipt = {
            "tool": action.tool,
            "executed": False,
            "verification": "environment_incomplete" if action.tool == "finish" else "help_unavailable",
            "message": "环境报告任务未完成"
            if action.tool == "finish" else
            "没有人可以帮忙，请换一种办法继续",
        }
        self.last_verification_measurements = {}
        self.motion_evidence = []
        self.last_skill_profile_evidence = {}
        self.receipts.append(receipt)
        return receipt

    def _execute(self, action: Candidate, receipt: dict, card: dict | None) -> None:
        if action.tool in ("finish", "ask_help"):
            receipt["executed"] = True
            return
        if action.tool == "card_next":
            if card is None:
                raise ValueError("card_next without a card")
            from robots.libero.v5_cards import resolve_card
            parsed = resolve_card(card, list(self.scene.entities.values()), self.held)
            if parsed is None:
                raise ValueError("card categories have no unique feasible measured binding")
            receipt.update(tool=parsed.tool, requested_tool="card_next")
            if self.skill_profiles is not None:
                from robots.libero.v5_skill_profiles import parameters_for
                obj = self.scene.entities.get(parsed.object or self.held)
                self.last_skill_profile_evidence["parameters"] = parameters_for(
                    self.skill_profiles, obj.name if obj else "empty"
                )
            for key in ("object", "target", "mode"):
                if getattr(parsed, key) is not None:
                    receipt[key] = getattr(parsed, key)
            self._execute(parsed, receipt, None)
            receipt["card_action"] = parsed.text()
            return
        if action.tool == "reperceive":
            self._refresh(sorted(self.scene.vocabulary))
            receipt.update(executed=True, verification="perception")
            return
        if action.tool in ("wrist_scan", "clear_view"):
            if not self.stagnation_recovery_v1:
                raise ValueError("measured stagnation recovery is disabled")
            if action.tool == "clear_view":
                self.move(self.recovery_view_pose, 0)
                self._refresh(sorted(self.scene.vocabulary))
            else:
                self.scan_wrist(sorted(self.scene.vocabulary))
            receipt.update(executed=True, verification="perception", recovery_view=action.tool)
            return
        if action.tool == "retreat":
            self.retreat()
            self.capture()
            receipt["executed"] = True
            return
        if action.tool == "release":
            moved = self.held
            self.p.release()
            self.held = None
            self.held_offset = None
            if moved:
                self._refresh([self.scene.entities[moved].name])
            else:
                self.capture()
            receipt["executed"] = True
            return
        obj = self.scene.entities[action.object]
        held_cache = (
            self.held_occlusion_v1 and action.tool in ("place", "adjust_place")
            and self.held == obj.id and self.held_offset is not None
        )
        if held_cache and not .005 <= self.p._last_obs_gripper <= .07:
            self.held = self.held_offset = None
            receipt.update(verification="failed", place_verified=False,
                           failure_reason="held_verification_lost")
            return
        measured_cache = (getattr(self.scene, "occluded_measurement_cache_v2", False)
                          and obj.geometry and obj.geometry.startswith("cached_perception"))
        if not obj.visible and not held_cache and not measured_cache:
            raise ValueError("object has no current visible measurement")
        if not obj.visible and measured_cache:
            receipt["object_geometry_source"] = "last_perception_measurement"
            receipt["object_measurement_step"] = obj.source_step
        if not obj.visible and held_cache:
            receipt["held_geometry_source"] = "last_visual_grasp_measurement_and_gripper"
        if action.tool in ("grasp", "regrasp_restage"):
            if getattr(self.scene, "region_anchor_cache_v1", False):
                self.scene.region_anchors.pop(obj.id, None)
            failures = [r for r in self.receipts[-10:] if r.get("object") == obj.id
                        and r.get("grasp_verified") is False]
            motion_action = action
            if self.grasp_retry_v1 and failures:
                self._refresh([obj.name])
                obj = self.scene.entities[obj.id]
                if not obj.visible and not (getattr(self.scene, "occluded_measurement_cache_v2", False)
                                           and obj.geometry and obj.geometry.startswith("cached_perception")):
                    raise ValueError("retry object missing after reperception")
                modes = ("direct", "above_10cm", "yaw_90")
                previous_mode = failures[-1].get("retry_staging", failures[-1].get("mode", "direct"))
                next_mode = modes[(modes.index(previous_mode) + 1) % len(modes)] if previous_mode in modes else "above_10cm"
                motion_action = replace(action, mode=next_mode)
                receipt["retry_staging"] = next_mode
            if self.target_cache_v1:
                self.target_cache = {e.id: e for e in self.scene.entities.values()
                                     if e.visible and e.id != obj.id and e.name != obj.name}
            height = (
                0.10
                if motion_action.mode == "above_10cm" or action.tool == "regrasp_restage"
                else 0.04
            )
            drawers = [
                e for e in self.scene.entities.values()
                if e.visible and e.name == "drawer"
                and all(e.lower[i] <= obj.xyz[i] <= e.upper[i] for i in range(3))
            ]
            from_drawer = motion_action.mode == "direct" and len(drawers) == 1
            if from_drawer:
                drawer = drawers[0]
                from_drawer = not any(
                    e.visible and e.name == obj.name and e.id != obj.id
                    and all(drawer.lower[i] <= e.xyz[i] <= drawer.upper[i] for i in range(3))
                    for e in self.scene.entities.values()
                )
            # An overhead waypoint enters the cabinet above an open drawer.
            # Let the contact policy approach the uniquely measured drawer
            # from the current pose; the selected object's binding stays public.
            if not from_drawer:
                approach = [obj.xyz[0], obj.xyz[1], obj.upper[2] + height]
                if self.grasp_approach_v1 or self.skill_profiles is not None:
                    approach, approach_kind, yaw = self.grasp_approach(obj, motion_action)
                    receipt["approach"] = approach_kind
                    if yaw is not None:
                        if not self.stage_wrist(yaw, receipt):
                            return
                if self.wrist_refine_v1 and self.wrist_measurement_standoff_v2:
                    # Measure from outside the near-contact crop, then use the
                    # same close approach after refining the measured object.
                    approach[2] = max(approach[2], obj.upper[2] + .15)
                if self.grasp_clearance_v1 and not self.grasp_safe_approach_v2:
                    approach[2] = self.grasp_transit_height(obj, approach)
                    lift = self.p._last_obs_eef_pos.copy()
                    lift[2] = approach[2]
                    self.move(lift, -1)
                if self.grasp_safe_approach_v2:
                    if not self.stage_grasp(obj, approach, receipt):
                        return
                else:
                    self.move(approach, -1)
                if self.p.env.terminated or self.p.env.truncated:
                    self.capture()
                    receipt.update(
                        executed=True,
                        stop="execution_interrupted",
                        grasp_verified=False,
                        verification="failed",
                    )
                    return
            if motion_action.mode == "yaw_90":
                if not self.stage_wrist(math.pi / 2, receipt):
                    return
            if self.wrist_refine_v1 and not (self.p.env.terminated or self.p.env.truncated):
                self.capture()
                refinement = {"guided_entity": obj} if self.wrist_geometry_prompt_v3 else {}
                self.scene.refresh([obj.name], camera_view="wrist", **refinement)
                refined = self.scene.entities.get(obj.id)
                cached_refinement = (refined is not None and getattr(self.scene, "occluded_measurement_cache_v2", False)
                                     and refined.geometry and refined.geometry.startswith("cached_perception"))
                if refined is None or not refined.visible and not cached_refinement:
                    raise ValueError("grasp object missing in close-up measurement")
                obj = refined
                receipt["refinement"] = "last_perception_cache_after_wrist_occlusion" if cached_refinement else "wrist_rgbd_before_contact"
                if not from_drawer:
                    refined_pose = self.grasp_approach(obj, motion_action)[0] if self.grasp_approach_v1 or self.skill_profiles is not None else [obj.xyz[0],obj.xyz[1],obj.upper[2]+height]
                    if self.grasp_clearance_v1:
                        refined_pose[2] = self.grasp_transit_height(obj, refined_pose)
                    if self.grasp_safe_approach_v2:
                        if not self.stage_grasp(obj, refined_pose, receipt):
                            return
                    else:
                        self.move(refined_pose,-1)
            result = self.vla_act(
                (f"pick up the {obj.name} from inside the drawer" if from_drawer
                 else f"pick up the {obj.name}" if self.grasp_short_prompt_v2 or (
                     (self.grasp_approach_v1 or self.skill_profiles is not None) and not self.grasp_local_prompt_v1)
                 else f"pick up the {obj.name} directly below the gripper"),
                self.max_chunks,
                "grasp_verified",
                obj,
                **({"lift_obstacle": drawers[0]} if from_drawer else {}),
            )
            if (not self.grasp_lift_check_v2 and not result["grasp_verified"] and not (
                self.p.env.terminated or self.p.env.truncated
            )):
                xyz = self.p._last_obs_eef_pos.copy()
                xyz[2] += 0.05
                self.move(xyz, 1)
            # The successful wrist trial is already the latest measurement.
            # No motion follows it: an extra primary-only refresh can hide the
            # same held object again and cause the next grasp to release it.
            if not (self.grasp_occlusion_scan_v1 and self._grasp_occlusion_scan_used
                    and result["grasp_verified"]):
                self._refresh([obj.name])
            verified = self.verify_grasp_measurement(obj)
            after = self.scene.entities.get(obj.id)
            receipt.update(
                result,
                stop=(
                    "grasp_verified"
                    if verified
                    else "verification_lost"
                    if result["grasp_verified"]
                    else result["stop"]
                ),
                grasp_verified=verified,
                verification="verified" if verified else "failed",
                gripper_opening=round(self.p._last_obs_gripper, 4),
                measured_z_rise_cm=round((after.xyz[2] - obj.xyz[2]) * 100, 2)
                if after and after.visible
                else None,
            )
            self.held = obj.id if verified else None
            # The median of a visible curved surface faces the camera. Align
            # measured footprint centres for placement rather than carrying
            # that surface bias into the destination's XY position.
            self.held_offset = (
                self.p._last_obs_eef_pos.copy() - np.asarray([
                    (after.lower[0] + after.upper[0]) / 2,
                    (after.lower[1] + after.upper[1]) / 2,
                    after.xyz[2],
                ])
                if verified
                else None
            )
            return
        if action.tool == "adjust_place":
            if not self.adjust_place_v1:
                raise ValueError("adjust_place is disabled")
            if self.held is None:
                cached_target = self.target_cache.get(action.target)
                recovery = {}
                self._execute(Candidate("grasp", obj.id, mode="above_10cm"), recovery, None)
                receipt["regrasp_verified"] = recovery.get("grasp_verified", False)
                if not recovery.get("grasp_verified"):
                    receipt.update(executed=True, place_verified=False, verification="failed")
                    return
                if cached_target is not None:
                    self.target_cache[action.target] = cached_target
            else:
                self.retreat()
                self._refresh([obj.name])
                measured = self.scene.entities[obj.id]
                if not measured.visible:
                    if not self.held_occlusion_v1:
                        raise ValueError("adjust_place held object missing after reperception")
                    if not .005 <= self.p._last_obs_gripper <= .07:
                        self.held = self.held_offset = None
                        receipt.update(verification="failed", place_verified=False,
                                       failure_reason="held_verification_lost")
                        return
                    receipt["held_geometry_source"] = "last_visual_grasp_measurement_and_gripper"
                else:
                    self.held_offset = self.p._last_obs_eef_pos.copy() - np.asarray([
                        (measured.lower[0] + measured.upper[0]) / 2,
                        (measured.lower[1] + measured.upper[1]) / 2, measured.xyz[2]])
            self._execute(Candidate("place", obj.id, action.target, action.mode), receipt, None)
            return
        if action.tool == "place":
            if self.held != obj.id:
                raise ValueError("place without a visually verified held object")
            target = (self.target_cache.get(action.target, self.scene.entities[action.target])
                      if self.target_cache_v1 else self.scene.entities[action.target])
            if not target.visible:
                raise ValueError("target not visible")
            if self.held_offset is None:
                raise ValueError("place without a measured held-object offset")
            offset = self.held_offset
            xyz = np.asarray(target.xyz) + offset
            # A visible-surface median can sit on the container wall.
            xyz[:2] = (np.asarray(target.lower[:2]) + target.upper[:2]) / 2 + offset[:2]
            xyz[2] = (
                target.upper[2]
                + max(0.015, (obj.upper[2] - obj.lower[2]) / 2)
                + offset[2]
            )
            if self.in_release_clearance_v1 and action.mode == "in":
                # Original drawer traces reach XY but stall during descent:
                # the low release waypoint may be obstructed near the rim.
                # Release above the measured rim, then verify the settled
                # placement; the servo tolerance and success check stay fixed.
                xyz[2] += 0.04
            above = xyz.copy()
            # Clear the measured rim while carrying the object, before descent.
            above[2] = max(
                self.p._last_obs_eef_pos[2],
                target.upper[2] + (obj.upper[2] - obj.lower[2]) / 2 + offset[2] + 0.10,
            )
            lift = self.p._last_obs_eef_pos.copy()
            lift[2] = above[2]
            if self.skill_profiles is not None:
                from robots.libero.v5_skill_profiles import parameters_for
                parameters = parameters_for(self.skill_profiles, obj.name)
                if "carry_lift_m" in parameters:
                    above[2] = max(self.p._last_obs_eef_pos[2],
                                   target.upper[2] + offset[2] + parameters["carry_lift_m"])
                    lift[2] = above[2]
            contact_in = (self.fixture_in_contact_v1 and action.mode == "in"
                          and target.name == "microwave" and target.geometry != "measured_cavity")
            if contact_in:
                # The measured shell is an articulation/semantic selector,
                # not an interior waypoint. Let the contact policy approach
                # the visible fixture; never label its shell as a cavity.
                contact = self.vla_act(f"put the {obj.name} inside the {target.name}",
                                       self.max_chunks, "released_object")
                receipt.update(**contact, placement_controller="fixture_contact/1-dev")
                if not contact["object_released"]:
                    if not .005 <= self.p._last_obs_gripper <= .07:
                        self.held = None
                        self.held_offset = None
                    receipt.update(place_verified=False, verification="unverified",
                                   verification_reason="contact_placement_release_not_observed")
                    return
            else:
                self.move(lift, 1)
                self.move(above, 1)
                if self.wrist_refine_v1 and not (self.p.env.terminated or self.p.env.truncated):
                    # A static destination stays at its pre-occlusion cached pose.
                    # Refine the carried object's measured extent from the wrist.
                    self.capture()
                    self.scene.refresh([obj.name], camera_view="wrist")
                    receipt["refinement"] = "wrist_rgbd_before_release; cached_destination"
                self.move(xyz, 1)
                if not (self.p.env.terminated or self.p.env.truncated):
                    self.p.release()
            self.held = None
            self.held_offset = None
            if not (self.p.env.terminated or self.p.env.truncated):
                self.retreat()
            self._refresh([obj.name, target.name])
            first = self.scene.entities.get(obj.id)
            wrist = first is None or not first.visible
            if wrist:
                self.scene.refresh([obj.name], placement=(obj, target))
                first = self.scene.entities.get(obj.id)
            t1 = self.scene.last_measurement_s[obj.name]
            if not (self.p.env.terminated or self.p.env.truncated):
                self.p.set_gripper(gripper=-1, steps=20)
            # The task can terminate before a wait action; still capture two
            # camera frames at distinct wall-clock times for visual stability.
            elapsed = time.perf_counter() - t1
            if elapsed < 0.3:
                time.sleep(0.3 - elapsed)
            self.capture()
            self.scene.refresh([obj.name], **({"placement": (obj, target)} if wrist else {}))
            second = self.scene.entities.get(obj.id)
            interval = self.scene.last_measurement_s[obj.name] - t1
            verifier = place_verified
            verification_rule = None
            if self.strict_place_v1:
                from robots.libero.v5_verification import strict_place_verified
                verifier = strict_place_verified
                verification_rule = "strict_place/1-dev"
            if self.strict_place_v2:
                from robots.libero.v5_verification import strict_place_verified_v2
                verifier = strict_place_verified_v2
                verification_rule = "strict_place/2-dev"
            if self.strict_place_v3:
                from robots.libero.v5_verification import strict_place_verified_v3
                verifier = strict_place_verified_v3
                verification_rule = "strict_place/3-dev"
            if self.strict_place_v4:
                from robots.libero.v5_verification import strict_place_verified_v4
                verifier = strict_place_verified_v4
                verification_rule = "strict_place/4-dev"
            if self.strict_place_v5:
                from robots.libero.v5_verification import strict_place_verified_v5
                verifier = strict_place_verified_v5
                verification_rule = "strict_place/5-dev"
            verified = verifier(
                first,
                second,
                target,
                self.p._last_obs_gripper,
                tuple(self.p._last_obs_eef_pos),
                interval,
                relation=action.mode,
            )
            from robots.libero.v5_state import entity_record
            from robots.libero.v5_verification import placement_verification_status, placement_unknown_reason
            self.last_verification_measurements = {
                "kind": "placement", "first": entity_record(first) if first else None,
                "second": entity_record(second) if second else None,
                "target": entity_record(target), "opening": self.p._last_obs_gripper,
                "eef_xyz": tuple(float(x) for x in self.p._last_obs_eef_pos),
                "interval_s": interval, "relation": action.mode,
                "target_cached": self.target_cache_v1 and action.target in self.target_cache,
                "source_step": self.toolkit._state.latest_step,
            }
            receipt.update(
                executed=True,
                place_verified=verified,
                verification=placement_verification_status(verified, first, second),
                measurement_interval_s=round(interval, 4),
                measurement_camera="wrist" if wrist else "agentview",
                **({"verification_rule": verification_rule} if verification_rule else {}),
                **({"verification_reason": placement_unknown_reason(first, second)}
                   if verified is None and self.strict_place_v5 else
                   {"verification_reason": "interior_containment_not_measured"}
                   if verified is None and (self.strict_place_v3 or self.strict_place_v4) else {}),
            )
            return
        if action.tool == "articulate":
            if self.target_cache_v1:
                self.target_cache = {key: value for key, value in self.target_cache.items()
                                     if key != obj.id and value.part_of != obj.id and key != obj.part_of}
            target_phrase = obj.name
            if self.fixture_part_prompt_v1 and target_phrase == "microwave":
                target_phrase = "microwave door"
            specific_part = obj.part_of is not None or re.search(
                r"\b(top|upper|middle|bottom|lower) drawer\b", obj.name
            ) is not None
            if ("cabinet" in obj.name or "drawer" in obj.name) and not (
                self.selected_fixture_target_v1 and specific_part
            ):
                part = re.search(
                    r"\b(top|upper|middle|bottom|lower) drawer\b",
                    self.instruction,
                    flags=re.IGNORECASE,
                )
                if part is not None:
                    target_phrase = f"{part.group(0).lower()} of the cabinet"
            endpoint_before = None
            if (self.articulate_verification_v2 and action.mode in ("open", "close")
                    and any(word in target_phrase for word in ("drawer", "microwave"))):
                parent = self.scene.entities.get(obj.part_of, obj)
                measured_phrase = "microwave door" if "microwave" in target_phrase else target_phrase
                endpoint_before = self.scene.measure_fixture_endpoint(parent, measured_phrase)
            result = self.vla_act(
                f"{action.mode.replace('_', ' ')} the {target_phrase}",
                self.max_chunks,
                "chunk_budget",
            )
            names = [obj.name]
            if getattr(self.scene, "fixture_handle_geometry_v3", False) and obj.part_of:
                names = [self.scene.entities[obj.part_of].name]
            if "cabinet" in obj.name:
                names.append("drawer")
            if self.held is not None and not 0.005 <= self.p._last_obs_gripper <= 0.07:
                lost = self.held
                self.held = None
                self.held_offset = None
                names.append(self.scene.entities[lost].name)
                receipt.update(
                    held_verification_lost=True,
                    lost_held_object=lost,
                    gripper_opening=round(self.p._last_obs_gripper, 4),
                )
            if (self.articulate_view_retreat_v1 and self.held is None
                    and not (self.p.env.terminated or self.p.env.truncated)):
                # Contact execution can leave the wrist over the moving face.
                # Release the fixture handle before restoring the viewing pose
                # so the retreat does not pull the door or drawer open again.
                self.p.release()
                receipt["post_contact_recovery"] = "release_fixture"
                if not (self.p.env.terminated or self.p.env.truncated):
                    self.retreat()
                    receipt["post_contact_recovery"] = "release_fixture_and_restore_view"
            self._refresh(names)
            receipt.update(**result, verification="unverified")
            if endpoint_before is not None:
                from robots.libero.v5_verification import measured_fixture_endpoint
                parent = self.scene.entities.get(obj.part_of or obj.id, obj)
                endpoint_after = self.scene.measure_fixture_endpoint(parent, measured_phrase)
                verified, evidence = measured_fixture_endpoint(endpoint_before, endpoint_after, action.mode,
                                                                drawer="drawer" in target_phrase)
                self.last_verification_measurements = {"articulation": evidence}
                receipt.update(articulate_verified=verified,
                               verification="unverified" if verified is None else "verified" if verified else "failed")
            elif self.articulate_verification_v1:
                from robots.libero.v5_verification import measured_articulation
                axis = (self.scene.fixture_front_axes.get(obj.part_of or obj.id)
                        if self.scene.fixture_front_geometry_v1 else self.scene.view_axes[1])
                verified, evidence = measured_articulation(obj, self.scene.entities.get(obj.id), action.mode, axis)
                receipt.update(articulate_verified=verified,
                               verification="unverified" if verified is None else "verified" if verified else "failed",
                               **evidence)
            return
        raise ValueError(f"unsupported v5 skill: {action.tool}")
