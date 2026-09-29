"""Perception cache and composite skills using RPent's LIBERO primitives."""

from __future__ import annotations

import base64
import math
import random
import re
import time
from dataclasses import replace

import numpy as np

from robots.libero.tools import dump_state
from robots.libero.v5_state import Candidate, Entity, grasp_verified, place_verified
from rpent.robots.components.sam3_client import Sam3Client


def category(name: str) -> str:
    """Use scene categories as segmentation vocabulary, stripping instance IDs."""
    return re.sub(r"\s+\d+$", "", name.replace("_", " ")).strip()


class MeasuredScene:
    """Stable episode-local IDs bound only to distinct measured instances."""

    def __init__(self, toolkit, rpc, seed: int) -> None:
        self.toolkit = toolkit
        self.rpc = rpc
        self.entities: dict[str, Entity] = {}
        self.calls = 0
        self.perception_s = 0.0
        self.last_measurement_s: dict[str, float] = {}
        self._ids = [f"e{i}" for i in range(1, 129)]
        random.Random(seed).shuffle(self._ids)

    def refresh(self, names: list[str]) -> None:
        """Segment only requested categories from a freshly captured RGB-D frame."""
        started = time.perf_counter()
        state = self.toolkit._state
        image = state.load_bytes("agentview_high.png")
        world = state.load("agentview_world_high.npz")
        encoded = base64.b64encode(image).decode("ascii")
        for name in sorted(set(names)):
            reply = self.rpc.call(
                "sam3.segment_all",
                kwargs={
                    "image_base64": encoded,
                    "text_prompt": name,
                    "min_score": 0.2,
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
                measured.append((tuple(centre), tuple(lower), tuple(upper)))
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
                xyz, lower, upper = measured[index]
                self.entities[eid] = Entity(
                    eid, name, xyz, lower, upper, source_step=state.latest_step
                )
                matched_old.add(eid)
                matched_new.add(index)
            for e in old:
                if e.id not in matched_old:
                    self.entities[e.id] = replace(e, visible=False)
            for index, (xyz, lower, upper) in enumerate(measured):
                if index not in matched_new:
                    if not self._ids:
                        raise ValueError("episode exhausted neutral ID pool")
                    eid = self._ids.pop()
                    self.entities[eid] = Entity(
                        eid, name, xyz, lower, upper, source_step=state.latest_step
                    )
            self.last_measurement_s[name] = time.perf_counter()
        self.perception_s += time.perf_counter() - started


class V5Executor:
    """Run finite skills and verify them with measured visual receipts."""

    def __init__(self, toolkit, scene: MeasuredScene, max_chunks: int = 40) -> None:
        self.toolkit = toolkit
        self.p = toolkit.primitives
        self.scene = scene
        self.held: str | None = None
        self.receipts: list[dict] = []
        self.max_chunks = max_chunks

    def capture(self) -> None:
        dump_state(self.p, self.toolkit._state)

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
            self._refresh([e.name for e in self.scene.entities.values()])
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
            if action.mode == "above_10cm" or action.tool == "regrasp_restage":
                self.move([obj.xyz[0], obj.xyz[1], obj.upper[2] + 0.10], -1)
            if action.mode == "yaw_90":
                self.p.rotate_wrist(target_yaw=math.pi / 2, gripper=-1)
            result = self.vla_act(
                f"grasp the {obj.name}", self.max_chunks, "grasp_verified", obj
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
            return
        if action.tool == "place":
            if self.held != obj.id:
                raise ValueError("place without a visually verified held object")
            target = self.scene.entities[action.target]
            if not target.visible:
                raise ValueError("target not visible")
            offset = self.p._last_obs_eef_pos - np.asarray(obj.xyz)
            xyz = np.asarray(target.xyz) + offset
            xyz[2] = (
                (target.lower[2] if action.mode == "in" else target.upper[2])
                + max(0.015, (obj.upper[2] - obj.lower[2]) / 2)
                + offset[2]
            )
            above = xyz.copy()
            above[2] += 0.10
            self.move(above, 1)
            self.move(xyz, 1)
            if not (self.p.env.terminated or self.p.env.truncated):
                self.p.release()
            self.held = None
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
            result = self.vla_act(
                f"{action.mode.replace('_', ' ')} the {obj.name}",
                self.max_chunks,
                "chunk_budget",
            )
            self._refresh([obj.name])
            receipt.update(**result, verification="unverified")
            return
        raise ValueError(f"unsupported v5 skill: {action.tool}")
