# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Action changes from RGB-D entities and measured gripper proprioception."""

from __future__ import annotations

import math


def public_action_snapshot(executor) -> dict:
    """Copy public measurements before a skill mutates the scene cache."""
    return {
        # Lightweight direct-executor fixtures may omit gripper telemetry;
        # treat that as the neutral closed reading while real runtime clients
        # always provide the measured value.
        "opening": float(getattr(executor.p, "_last_obs_gripper", 0.0)),
        "held": executor.held,
        "entities": dict(getattr(executor.scene, "entities", {})),
    }


def measured_action_effect(before: dict, after: dict, receipt: dict) -> dict:
    """Record visible displacement; missing geometry is explicitly unknown.

    Repeated frame IDs and cached occluded poses cannot prove an object did
    not move. The no_effect tag means no change was measured, not physical
    impossibility or an oracle judgment about task progress.
    """
    changes, furniture, missing = {}, {}, []
    changed = before["held"] != after["held"] or abs(before["opening"] - after["opening"]) >= .005
    relevant = {receipt.get("object"), receipt.get("target"), before["held"], after["held"]} - {None}
    relevant |= {eid for scene in (before, after) for eid, entity in scene["entities"].items()
                 if entity.part_of in relevant}
    for eid in sorted(relevant):
        previous, current = before["entities"].get(eid), after["entities"].get(eid)
        if (previous is None or current is None or not previous.visible or not current.visible
                or current.source_step <= previous.source_step):
            missing.append(eid)
            continue
        changes[eid] = [round((a - b) * 100, 2) for a, b in zip(current.xyz, previous.xyz)]
        changed |= math.dist(current.xyz, previous.xyz) >= .01 or any(
            math.dist(a, b) >= .01 for a, b in ((current.lower, previous.lower), (current.upper, previous.upper)))
        if current.part_of or any(word in current.name for word in ("drawer", "door", "stove")):
            furniture[eid] = {"dxyz_cm": changes[eid], "verified": receipt.get("articulate_verified")}
    measured = {
        "gripper_m": [round(before["opening"], 4), round(after["opening"], 4)],
        "held": [before["held"], after["held"]],
        "dxyz_cm": changes,
    }
    endpoint = receipt.get("articulation_state")
    if endpoint and receipt.get("object"):
        first, second = endpoint.get("before"), endpoint.get("after")
        furniture[receipt["object"]] = {"state": endpoint.get("state", "unmeasured"),
            "verified": receipt.get("articulate_verified"),
            "before": first, "after": second}
        if (first and second and first.get("visible") and second.get("visible")
                and second.get("source_step", -1) > first.get("source_step", -1)):
            previous_red = first.get("features", {}).get("red_fraction")
            current_red = second.get("features", {}).get("red_fraction")
            if previous_red is not None and current_red is not None:
                changed |= abs(current_red - previous_red) >= .02
    if furniture:
        measured["furniture"] = furniture
    if missing:
        measured["unmeasured_entities"] = missing
    return {"effect": "measured_change" if changed else "no_effect", "measurement": measured,
            "receipt_version": "measured_action/1"}
