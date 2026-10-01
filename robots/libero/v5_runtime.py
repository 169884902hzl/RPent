# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Perception cache and composite skills using RPent's LIBERO primitives."""

from __future__ import annotations

import base64
import math
import random
import re
import time
from dataclasses import replace

import numpy as np

from robots.libero.v5_state import Candidate, Entity, grasp_verified, place_verified
from rpent.robots.components.sam3_client import Sam3Client


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
        "butter": "small orange box",
        "milk": "orange milk carton",
        "chocolate pudding": "flat brown box",
        "porcelain mug": "porcelain mug",
        "white yellow mug": "white and yellow mug",
        "cabinet": "small black cabinet",
        "drawer": "drawer of the small black cabinet",
        "microwave": "microwave door",
        "ramekin": "small ramekin bowl",
        "cookie box": "small box of cookies",
        "moka pot": "silver moka coffee pot",
        "red coffee mug": "red ceramic coffee mug",
        "white yellow mug": "white and yellow ceramic mug",
        "black book": "black closed book",
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
    for fixture in ("drawer", "cabinet", "microwave", "stove"):
        if re.search(r"\b" + fixture + r"\b", instruction, re.IGNORECASE):
            result.add(fixture)
    return sorted(result)


def segmentation_retry_prompt(name: str) -> str:
    """Use a concrete visual synonym when the first open-vocabulary query is empty."""
    return {
        "bowl": "black bowl on the tabletop",
        "plate": "white plate with red rings",
        "cookie box": "small box of cookies",
        "ramekin": "small fluted bowl",
        "cabinet": "black cabinet with drawers",
        "drawer": "open drawer of the small black cabinet",
        "microwave": "open microwave door",
        "cream cheese": "small blue rectangular cream cheese box",
        "barbecue sauce": "barbecue sauce bottle",
        "butter": "small orange box",
        "milk": "milk carton",
        "chocolate pudding": "brown rectangular box",
        "moka pot": "silver octagonal moka pot coffee maker",
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

    def __init__(self, toolkit, rpc, seed: int) -> None:
        self.toolkit = toolkit
        self.rpc = rpc
        self.entities: dict[str, Entity] = {}
        self.vocabulary: set[str] = set()
        self.calls = 0
        self.perception_s = 0.0
        self.last_measurement_s: dict[str, float] = {}
        self._scores: dict[str, float] = {}
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

    def refresh(self, names: list[str]) -> None:
        """Segment only requested categories from a freshly captured RGB-D frame."""
        started = time.perf_counter()
        self.vocabulary.update(names)
        state = self.toolkit._state
        image = state.load_bytes("agentview_high.png")
        world = state.load("agentview_world_high.npz")
        encoded = base64.b64encode(image).decode("ascii")
        for name in sorted(set(names)):
            prompt = segmentation_prompt(name)
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
            if not reply.get("instances"):
                retry_prompt = segmentation_retry_prompt(name)
                if retry_prompt != prompt:
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
            measured = []
            for item in reply["instances"]:
                mask = Sam3Client._decode_result(item).mask
                if mask is None or mask.shape != world.shape[:2]:
                    raise ValueError("SAM/depth image dimensions differ")
                points = world[mask].astype(np.float64)
                points = points[
                    np.isfinite(points).all(axis=1)
                    & (np.abs(points).sum(axis=1) > 1e-6)
                ]
                if len(points) < 10:
                    continue
                lower, upper = np.quantile(points, (0.02, 0.98), axis=0)
                centre = np.median(points, axis=0)
                score = float(item.get("score", 0.0))
                candidate = (tuple(centre), tuple(lower), tuple(upper), score)
                # SAM can return nested/duplicate masks for one package. Keep
                # one measured instance per nearby physical centre.
                if any(math.dist(candidate[0], old_item[0]) <= 0.02 for old_item in measured):
                    continue
                measured.append(candidate)
            old = [e for e in self.entities.values() if e.name == name]
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
                xyz, lower, upper, score = measured[index]
                self.entities[eid] = Entity(
                    eid, name, xyz, lower, upper, source_step=state.latest_step
                )
                self._scores[eid] = score
                matched_old.add(eid)
                matched_new.add(index)
            for e in old:
                if e.id not in matched_old:
                    self.entities[e.id] = replace(e, visible=False)
            for index, (xyz, lower, upper, score) in enumerate(measured):
                if index not in matched_new:
                    near = [
                        e for e in self.entities.values()
                        if e.visible
                        and math.dist(e.xyz, xyz) <= 0.02
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
                            source_step=state.latest_step
                        )
                        self._scores[existing.id] = score
                        continue
                    if not self._ids:
                        raise ValueError("episode exhausted neutral ID pool")
                    eid = self._ids.pop()
                    self.entities[eid] = Entity(
                        eid, name, xyz, lower, upper, source_step=state.latest_step
                    )
                    self._scores[eid] = score
            self.last_measurement_s[name] = time.perf_counter()
        self.perception_s += time.perf_counter() - started


class V5Executor:
    """Run finite skills and verify them with measured visual receipts."""

    def __init__(
        self,
        toolkit,
        scene: MeasuredScene,
        max_chunks: int = 40,
        instruction: str = "",
    ) -> None:
        self.toolkit = toolkit
        self.p = toolkit.primitives
        self.scene = scene
        self.held: str | None = None
        self.held_offset: np.ndarray | None = None
        self.receipts: list[dict] = []
        self.max_chunks = max_chunks
        self.instruction = instruction

    def capture(self) -> None:
        # Composite skills bypass execute_tool; publish their native termination
        # through the toolkit before scoring or taking the next measurement.
        self.toolkit.get_env_state(
            command={"action": "v5_measurement"}, result={}, elapsed_s=0.0
        )

    def vla_act(
        self, prompt: str, max_chunks: int, stop: str, obj: Entity | None = None
    ) -> dict:
        """Bound contact execution; a held-object stop requires visual evidence."""
        if stop not in ("grasp_verified", "chunk_budget"):
            raise ValueError(f"unsupported contact stop: {stop}")
        if stop == "grasp_verified" and obj is None:
            raise ValueError("visual grasp stop requires the measured object")
        chunks = 0
        previous_opening = self.p._last_obs_gripper
        stable_chunks = 0
        verified = False
        for _ in range(max_chunks):
            if self.p.env.terminated or self.p.env.truncated:
                break
            self.p._vlm_chunk(prompt)
            chunks += 1
            opening = self.p._last_obs_gripper
            stable_chunks = (
                stable_chunks + 1 if abs(opening - previous_opening) <= 0.002 else 0
            )
            previous_opening = opening
            if (
                stop == "grasp_verified"
                and stable_chunks >= 2
                and 0.005 <= opening <= 0.07
            ):
                if not (self.p.env.terminated or self.p.env.truncated):
                    xyz = self.p._last_obs_eef_pos.copy()
                    xyz[2] += 0.05
                    self.move(xyz, 1)
                self._refresh([obj.name])
                verified = grasp_verified(
                    obj, self.scene.entities.get(obj.id), self.p._last_obs_gripper
                )
                if verified:
                    break
                stable_chunks = 0
        return {
            "executed": chunks > 0,
            "chunks": chunks,
            "stop": stop,
            **({"grasp_verified": verified} if stop == "grasp_verified" else {}),
        }

    def move(self, xyz: tuple | list, gripper: float) -> dict:
        """Respect the RPent planar servo range by splitting measured waypoints."""
        target = np.asarray(xyz, dtype=float)
        for _ in range(8):
            current = self.p._last_obs_eef_pos.copy()
            distance = float(np.linalg.norm((target - current)[:2]))
            if distance <= 0.27:
                break
            mid = current + (target - current) * (0.25 / distance)
            mid[2] = max(current[2], target[2])
            self.p.move_to(mid.tolist(), gripper=gripper)
            if self.p.env.terminated or self.p.env.truncated:
                return {"executed": True, "interrupted": True}
        if self.p.env.terminated or self.p.env.truncated:
            return {"executed": False, "interrupted": True}
        result = self.p.move_to(target.tolist(), gripper=gripper)
        if result["final_dist_m"] > 0.02:
            raise RuntimeError(
                f"servo did not reach measured waypoint: {result['final_dist_m']} m"
            )
        return result

    def retreat(self) -> None:
        xyz = self.p._last_obs_eef_pos.copy()
        xyz[2] += 0.10
        self.move(xyz, 1 if self.held else -1)

    def _refresh(self, names: list[str]) -> None:
        self.capture()
        self.scene.refresh(names)

    def execute(self, action: Candidate, card: dict | None = None) -> dict:
        """Return a typed receipt, with no official success predicate in it."""
        receipt = {"tool": action.tool, "executed": False, "verification": "unverified"}
        for key in ("object", "target", "mode"):
            value = getattr(action, key)
            if value is not None:
                receipt[key] = value
        try:
            self._execute(action, receipt, card)
        except Exception as error:
            receipt.update(
                error=f"{type(error).__name__}: {error}", verification="execution_error"
            )
            if action.tool in ("grasp", "regrasp_restage"):
                receipt["grasp_verified"] = False
            self.capture()
        self.receipts.append(receipt)
        return receipt

    def _execute(self, action: Candidate, receipt: dict, card: dict | None) -> None:
        if action.tool in ("finish", "ask_help"):
            receipt["executed"] = True
            return
        if action.tool == "card_next":
            if card is None:
                raise ValueError("card_next without a card")
            parsed = Candidate(**card["action"])
            if parsed.tool == "card_next":
                raise ValueError("recursive card_next")
            self._execute(parsed, receipt, None)
            receipt["card_action"] = parsed.text()
            return
        if action.tool == "reperceive":
            self._refresh(sorted(self.scene.vocabulary))
            receipt.update(executed=True, verification="perception")
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
        if not obj.visible:
            raise ValueError("object has no current visible measurement")
        if action.tool in ("grasp", "regrasp_restage"):
            height = (
                0.10
                if action.mode == "above_10cm" or action.tool == "regrasp_restage"
                else 0.04
            )
            self.move([obj.xyz[0], obj.xyz[1], obj.upper[2] + height], -1)
            if action.mode == "yaw_90":
                self.p.rotate_wrist(target_yaw=math.pi / 2, gripper=-1)
            result = self.vla_act(
                f"pick up the {obj.name} directly below the gripper",
                self.max_chunks,
                "grasp_verified",
                obj,
            )
            if not result["grasp_verified"] and not (
                self.p.env.terminated or self.p.env.truncated
            ):
                xyz = self.p._last_obs_eef_pos.copy()
                xyz[2] += 0.05
                self.move(xyz, 1)
            self._refresh([obj.name])
            after = self.scene.entities.get(obj.id)
            verified = grasp_verified(obj, after, self.p._last_obs_gripper)
            receipt.update(
                result,
                grasp_verified=verified,
                verification="verified" if verified else "failed",
                gripper_opening=round(self.p._last_obs_gripper, 4),
                measured_z_rise_cm=round((after.xyz[2] - obj.xyz[2]) * 100, 2)
                if after and after.visible
                else None,
            )
            self.held = obj.id if verified else None
            self.held_offset = (
                self.p._last_obs_eef_pos.copy() - np.asarray(after.xyz)
                if verified
                else None
            )
            return
        if action.tool == "place":
            if self.held != obj.id:
                raise ValueError("place without a visually verified held object")
            target = self.scene.entities[action.target]
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
            above = xyz.copy()
            # Clear the measured rim while carrying the object, before descent.
            above[2] = max(
                self.p._last_obs_eef_pos[2],
                target.upper[2] + (obj.upper[2] - obj.lower[2]) / 2 + offset[2] + 0.10,
            )
            lift = self.p._last_obs_eef_pos.copy()
            lift[2] = above[2]
            self.move(lift, 1)
            self.move(above, 1)
            self.move(xyz, 1)
            if not (self.p.env.terminated or self.p.env.truncated):
                self.p.release()
            self.held = None
            self.held_offset = None
            if not (self.p.env.terminated or self.p.env.truncated):
                self.retreat()
            self._refresh([obj.name, target.name])
            first = self.scene.entities.get(obj.id)
            t1 = self.scene.last_measurement_s[obj.name]
            # The task can terminate before a wait action; still capture two
            # camera frames at distinct wall-clock times for visual stability.
            elapsed = time.perf_counter() - t1
            if elapsed < 0.3:
                time.sleep(0.3 - elapsed)
            self._refresh([obj.name])
            second = self.scene.entities.get(obj.id)
            interval = self.scene.last_measurement_s[obj.name] - t1
            verified = place_verified(
                first,
                second,
                target,
                self.p._last_obs_gripper,
                tuple(self.p._last_obs_eef_pos),
                interval,
            )
            receipt.update(
                executed=True,
                place_verified=verified,
                verification="verified" if verified else "failed",
                measurement_interval_s=round(interval, 4),
            )
            return
        if action.tool == "articulate":
            target_phrase = obj.name
            if "cabinet" in obj.name or "drawer" in obj.name:
                part = re.search(
                    r"\b(top|upper|middle|bottom|lower) drawer\b",
                    self.instruction,
                    flags=re.IGNORECASE,
                )
                if part is not None:
                    target_phrase = f"{part.group(0).lower()} of the cabinet"
            result = self.vla_act(
                f"{action.mode.replace('_', ' ')} the {target_phrase}",
                self.max_chunks,
                "chunk_budget",
            )
            self._refresh([obj.name])
            receipt.update(**result, verification="unverified")
            return
        raise ValueError(f"unsupported v5 skill: {action.tool}")
