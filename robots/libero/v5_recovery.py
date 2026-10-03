# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Detect unchanged measured scenes without consulting task predicates."""

from __future__ import annotations

import math


class MeasuredRecovery:
    """Count measured stagnation and bound repeated no-op perception choices."""

    def __init__(self) -> None:
        self.no_progress_steps = 0
        self.unchanged_reperceptions = 0
        self.reperceive_cooldown = 0
        self.ineffective_actions = 0

    @staticmethod
    def snapshot(entities, held, opening) -> dict:
        return {"entities": {e.id: (e.name, e.visible, e.xyz, e.lower, e.upper)
                             for e in entities}, "held": held, "opening": opening}

    @staticmethod
    def unchanged(before: dict, after: dict) -> bool:
        if before["held"] != after["held"] or abs(before["opening"] - after["opening"]) > .005:
            return False
        if before["entities"].keys() != after["entities"].keys():
            return False
        for eid, previous in before["entities"].items():
            current = after["entities"][eid]
            if previous[:2] != current[:2]:
                return False
            if previous[1] and any(math.dist(a, b) > .01 for a, b in zip(previous[2:], current[2:])):
                return False
        return True

    def observe(self, action, before: dict, after: dict) -> None:
        same = self.unchanged(before, after)
        self.no_progress_steps = self.no_progress_steps + 1 if same else 0
        if same and action.tool in ("reperceive", "ask_help", "retreat", "wrist_scan", "clear_view", "regrasp_restage"):
            self.ineffective_actions += 1
        self.reperceive_cooldown = max(0, self.reperceive_cooldown - 1)
        if not same:
            self.unchanged_reperceptions = 0
        elif action.tool == "reperceive":
            self.unchanged_reperceptions += 1
        if self.unchanged_reperceptions >= 2:
            self.reperceive_cooldown = 3
            self.unchanged_reperceptions = 0

    def status(self) -> dict:
        return {"no_progress_steps": self.no_progress_steps,
                "reperceive_cooldown": self.reperceive_cooldown}
