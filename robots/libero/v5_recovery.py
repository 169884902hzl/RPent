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
        self._failure_references: dict[str, dict] = {}
        self._failure_entities: dict[str, set[str]] = {}

    @staticmethod
    def snapshot(entities, held, opening) -> dict:
        entities = list(entities)
        return {"entities": {e.id: (e.name, e.visible, e.xyz, e.lower, e.upper)
                             for e in entities}, "held": held, "opening": opening,
                "parents": {e.id: e.part_of for e in entities if e.part_of}}

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
        endpoint = (receipt or {}).get("articulation_state") or {}
        first, second = endpoint.get("before"), endpoint.get("after")
        fixture_change = False
        if (first and second and first.get("src") == second.get("src") == "perception"
                and first.get("entity") == second.get("entity") and first.get("visible") and second.get("visible")
                and second.get("source_step", -1) > first.get("source_step", -1)):
            previous_red = first.get("features", {}).get("red_fraction")
            current_red = second.get("features", {}).get("red_fraction")
            fixture_change = (previous_red is not None and current_red is not None
                              and abs(current_red - previous_red) >= .02)
        same = same and not fixture_change
        if self.measurement_progress_blocking:
            if self._progress_reference is None:
                self._progress_reference = before
            key = action.text()
            current_failed = self.failed(receipt or {})
            # A remeasurement of an unrelated entity must not make a failed
            # grasp/place eligible again. In saved development traces a static
            # cabinet's visible box changed by 36 cm during clear_view, which
            # previously released every grasp failure on an unchanged bowl.
            for failed_key in tuple(self.action_failures):
                if failed_key == key and current_failed:
                    continue
                reference = self._failure_references.get(failed_key, self._progress_reference)
                relevant = self._failure_entities.get(failed_key, set())
                fixture_relevant = fixture_change and (not relevant or action.object in relevant)
                if fixture_relevant or not self.action_scene_unchanged(reference, after, relevant):
                    self.action_failures.pop(failed_key)
                    self.blocked_actions.discard(failed_key)
                    self._failure_references.pop(failed_key, None)
                    self._failure_entities.pop(failed_key, None)
            if fixture_change or not self.scene_unchanged(self._progress_reference, after):
                self._progress_reference = after
            self._observe_failure(action, receipt or {})
            if key in self.action_failures:
                self._failure_references[key] = after
                self._failure_entities[key] = {e for e in (action.object, action.target) if e is not None}
            else:
                self._failure_references.pop(key, None)
                self._failure_entities.pop(key, None)
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

    @staticmethod
    def failed(receipt: dict) -> bool:
        return receipt.get("verification") in {"failed", "execution_error"} or any(
            receipt.get(key) is False
            for key in ("grasp_verified", "place_verified", "articulate_verified")
        ) or receipt.get("effect") == "no_effect"

    @classmethod
    def action_scene_unchanged(cls, before: dict, after: dict, relevant: set[str]) -> bool:
        """Gate a failed skill on its objects and measured fixture parts.

        Control actions without entity arguments retain the whole-scene gate.
        This internal reference adds no model-visible row or field.
        """
        if not relevant:
            return cls.scene_unchanged(before, after)
        relevant = relevant | {eid for state in (before, after)
                               for eid, parent in state.get("parents", {}).items() if parent in relevant}
        return cls.scene_unchanged(
            {**before, "entities": {eid: e for eid, e in before["entities"].items() if eid in relevant}},
            {**after, "entities": {eid: e for eid, e in after["entities"].items() if eid in relevant}},
        )

    def _observe_failure(self, action, receipt: dict) -> None:
        # Missing verification is not a failed physical branch. Only measured
        # no-effect or an explicit failed verification can suppress an action.
        failed = receipt.get("verification") in {"failed", "execution_error"} or any(
            receipt.get(key) is False
            for key in ("grasp_verified", "place_verified", "articulate_verified")
        )
        no_effect = receipt.get("effect") == "no_effect"
        key = action.text()
        if failed or no_effect:
            previous = self.action_failures.get(key, {"count": 0})
            reason = receipt.get("failure_reason") or (
                "execution_error" if receipt.get("verification") == "execution_error"
                else "verification_failed" if failed else "no_effect")
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
