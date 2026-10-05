# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Detect unchanged measured scenes without consulting task predicates."""

from __future__ import annotations

import math


class MeasuredRecovery:
    """Count measured stagnation and bound repeated no-op perception choices."""

    def __init__(self, *, measurement_progress_blocking: bool = False) -> None:
        self.no_progress_steps = 0
        self.unchanged_reperceptions = 0
        self.reperceive_cooldown = 0
        self.ineffective_actions = 0
        self.measurement_progress_blocking = measurement_progress_blocking
        self.action_failures: dict[str, dict] = {}
        self.blocked_actions: set[str] = set()
        self._progress_reference: dict | None = None

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

    @staticmethod
    def scene_unchanged(before: dict, after: dict) -> bool:
        """Compare the scene to its last progress reference, using public data.

        A held-identity, visibility or entity change is progress. Otherwise a
        measured centre or box corner must move at least 2 cm. Camera frame
        counters, pure EEF motion and empty-gripper opening do not release a
        failed-action block. Small consecutive moves accumulate because the
        reference is updated only after a change reaches this threshold.
        """
        if before["held"] != after["held"]:
            return False
        if before["entities"].keys() != after["entities"].keys():
            return False
        for eid, previous in before["entities"].items():
            current = after["entities"][eid]
            if previous[:2] != current[:2]:
                return False
            if previous[1] and any(math.dist(a, b) >= .02 for a, b in zip(previous[2:], current[2:])):
                return False
        return True

    def observe(self, action, before: dict, after: dict, receipt: dict | None = None) -> None:
        same = self.unchanged(before, after)
        if self.measurement_progress_blocking:
            if self._progress_reference is None:
                self._progress_reference = before
            if not self.scene_unchanged(self._progress_reference, after):
                self.action_failures.clear()
                self.blocked_actions.clear()
                self._progress_reference = after
            else:
                self._observe_failure(action, receipt or {})
        self.no_progress_steps = self.no_progress_steps + 1 if same else 0
        if same and action.tool in ("reperceive", "ask_help", "retreat", "wrist_scan", "clear_view", "regrasp_restage"):
            self.ineffective_actions += 1
        self.reperceive_cooldown = max(0, self.reperceive_cooldown - 1)
        if not same:
            self.unchanged_reperceptions = 0
        elif action.tool == "reperceive":
            self.unchanged_reperceptions += 1
        if self.unchanged_reperceptions >= 2:
            if not self.measurement_progress_blocking:
                self.reperceive_cooldown = 3
            self.unchanged_reperceptions = 0

    def _observe_failure(self, action, receipt: dict) -> None:
        # Missing verification is not a failed physical branch. Only measured
        # no-effect or an explicit failed verification can suppress an action.
        failed = receipt.get("verification") == "failed" or any(
            receipt.get(key) is False
            for key in ("grasp_verified", "place_verified", "articulate_verified")
        )
        no_effect = receipt.get("effect") == "no_effect"
        if receipt.get("verification") == "execution_error":
            return
        key = action.text()
        if failed or no_effect:
            previous = self.action_failures.get(key, {"count": 0})
            reason = receipt.get("failure_reason") or (
                "verification_failed" if failed else "no_effect")
            self.action_failures[key] = {"count": previous["count"] + 1, "kind": reason}
            if self.action_failures[key]["count"] >= 2:
                self.blocked_actions.add(key)
        elif key not in self.blocked_actions and (receipt.get("verification") == "verified" or any(
            receipt.get(key) is True
            for key in ("grasp_verified", "place_verified", "articulate_verified")
        )):
            self.action_failures.pop(key, None)

    def status(self) -> dict:
        result = {"no_progress_steps": self.no_progress_steps,
                  "reperceive_cooldown": self.reperceive_cooldown}
        if self.measurement_progress_blocking:
            result.update(blocked_actions=sorted(self.blocked_actions),
                          action_failures={key: dict(value) for key, value in self.action_failures.items()})
        return result
