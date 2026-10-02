# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Evaluation-only recipe semantics; measured init0 anchors replace XYZ replay."""

import math
import re

from robots.libero.v5_runtime import category


def grasp_category(prompt):
    text = prompt.lower().strip().rstrip(".")
    match = re.match(r"(?:pick up|pick|grasp|lift|take)\s+(?:the\s+)?(.+)", text)
    if not match:
        return None
    phrase = re.split(r"\s+(?:and|from|between|on|in|near|next to|to)\s+", match[1])[0]
    names = [(r"\bbowl\b", "bowl"), (r"\bcream cheese\b", "cream cheese"),
             (r"\bmoka|coffee pot", "moka pot"), (r"\bplate\b", "plate"),
             (r"\bpan\b", "frypan"), (r"\bbook\b", "black book")]
    for pattern, name in names:
        if re.search(pattern, phrase):
            return name
    # Preserve distinctions between mug/grocery categories when present.
    value = category(phrase)
    if any(word in value for word in ("mug", "bottle", "soup", "sauce", "milk", "butter", "pudding", "dressing")):
        return value
    return None


def measured_init0_anchors(audit):
    """Accept only declared camera/back-project measurements, never final poses."""
    localization = audit.get("localization") or {}
    method = localization.get("method", "").lower()
    if not any(word in method for word in ("back_project", "back-projection", "perception", "wrist")):
        return []
    anchors = []
    for key, value in (localization.get("agentview_samples") or {}).items():
        if not re.search(r"xyz(?:_median)?(?:_approx)?$", key):
            continue
        if not isinstance(value, list) or len(value) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in value):
            continue
        label = re.sub(r"_xyz(?:_median)?(?:_approx)?$", "", key)
        label = re.sub(r"^(?:target|other)_", "", label)
        anchors.append({"category": category(label), "xyz": value,
                        "source": "localization.agentview_samples." + key,
                        "measurement_method": method})
    return anchors


def convert_recipe(commands, audit):
    """Fold primitive motions into typed skills, retaining every uncertain case."""
    anchors = measured_init0_anchors(audit)
    held, last_xyz = None, None
    steps, evidence, unmapped = [], [], []
    for index, command in enumerate(commands, 1):
        tool = command.get("action")
        if tool in ("view_env_state", "view_camera_meta", "segment", "back_project", "read_image"):
            evidence.append({"line": index, "mapping": "observation only"})
        elif tool in ("move_to", "move_pose") and command.get("xyz") is not None:
            last_xyz = command["xyz"]
            evidence.append({"line": index, "mapping": "staging/carry waypoint, coordinate discarded"})
        elif tool == "set_gripper" and command.get("gripper", 0) > 0:
            evidence.append({"line": index, "mapping": "grip reinforcement"})
        elif tool == "pi0_pick":
            obj = grasp_category(command.get("prompt", ""))
            if obj is None:
                unmapped.append({"line": index, "reason": "no deterministic grasp category", "command": command})
                continue
            held = obj
            steps.append({"skill": "grasp", "object_category": obj, "mode": "direct"})
            evidence.append({"line": index, "mapping": "grasp category", "prompt": command.get("prompt"), "category": obj})
        elif tool == "release" or tool == "set_gripper" and command.get("gripper", 0) < 0:
            # Do not call every gripper-open waypoint a completed placement.
            if held is None or last_xyz is None:
                unmapped.append({"line": index, "reason": "release has no preceding held category/waypoint", "command": command})
                continue
            options = [(math.dist(last_xyz[:2], anchor["xyz"][:2]), anchor) for anchor in anchors
                       if anchor["category"] != held]
            options.sort(key=lambda item: item[0])
            if not options or options[0][0] > .12 or len(options) > 1 and options[1][0] - options[0][0] < .02:
                unmapped.append({"line": index, "reason": "nearest measured init0 destination absent or ambiguous", "command": command})
                continue
            distance, target = options[0]
            mode = "in" if any(word in target["category"] for word in ("drawer", "basket", "microwave", "compartment")) else "on"
            steps.append({"skill": "place", "object_category": held, "target_category": target["category"], "mode": mode})
            evidence.append({"line": index, "mapping": "release nearest measured init0 destination",
                             "target_category": target["category"], "xy_distance_m": distance,
                             "anchor_source": target["source"]})
            held = None
        elif tool in ("retreat", "finish"):
            steps.append({"skill": tool})
            evidence.append({"line": index, "mapping": tool})
        else:
            unmapped.append({"line": index, "reason": "primitive cannot be expressed by an existing typed skill", "command": command})
    if audit.get("libero_terminated") is True and not unmapped and steps and steps[-1]["skill"] != "finish":
        steps.append({"skill": "finish"})
    return steps, evidence, unmapped
