# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Opt-in public drawer endpoint observation and neutral stability hold.

The saved drawer selection trajectories expose a face-identity failure for
close: a static rear panel can pass the signed endpoint test. Until a public
identity verifier is qualified, close remains unmeasured. This module neither
reads private joints nor uses native task success to admit a stop.
"""

from __future__ import annotations

import copy

import numpy as np

from robots.libero.v5_verification import measured_fixture_endpoint


VERSION = "public-drawer-endpoint-hold/9-dev"
STABILITY_CONTROLS = 6
CONTROL_DT_S = .05


def measure_public_drawer_endpoint(before, after, mode):
    """Retain signed-v6 thresholds but abstain on unqualified face identity."""
    verdict, evidence = measured_fixture_endpoint(
        before, after, mode, drawer=True, signed_drawer_v6=True)
    evidence = {**evidence, "admission_version": VERSION,
                "private_inputs_used_for_control": False,
                "geometric_endpoint_candidate": verdict}
    if verdict is None:
        return None, evidence
    for sample in (before, after):
        if sample.get("source") != "perception":
            return None, {**evidence, "reason": "public_measurement_provenance_missing"}
    if (before.get("anchor_parent") != after.get("anchor_parent")
            or before.get("anchor_part") != after.get("anchor_part")
            or after.get("current_part") != before.get("anchor_part")
            or after.get("current_part_source_step") != after["source_step"]):
        return None, {**evidence, "reason": "current_selected_panel_binding_missing"}
    if mode == "close":
        # Two-view support and stable entity IDs do not solve this identity
        # problem: the saved CPU audit still finds false positives with both.
        # Do not turn an experimental geometry estimate into a verified close.
        views = after.get("views", {})
        supported = [camera for camera in ("agentview", "wrist")
                     if views.get(camera, {}).get("moving")]
        return None, {**evidence, "reason": "drawer_close_face_identity_not_qualified",
                      "moving_face_support_cameras": supported,
                      "close_verifier_qualification": "not_passed"}
    return verdict, evidence


class DrawerEndpointHold:
    """Observe every completed contact block; hold immediately at an endpoint."""

    def __init__(self, executor, parent, phrase, mode, before):
        self.executor, self.parent, self.phrase = executor, parent, phrase
        self.mode, self.before = mode, copy.deepcopy(before)
        self.bounds = {"lower": list(parent.lower), "upper": list(parent.upper)}
        self.records = []
        self.before_public_frame = self.public_frame()

    def public_frame(self):
        # Share the explicit RGB-D/proprioception artifact contract with the
        # CPU temporal encoder. Numeric features are recomputed offline using
        # that same encoder; only their public inputs are persisted here.
        from robots.libero.v5_temporal_verifier import public_frame

        frame = public_frame(self.executor, self.bounds, profile="world_xy_grid_v1")
        frame.pop("features", None)
        return frame

    def capture(self, chunks, phase):
        ex = self.executor
        ex._refresh([self.parent.name])
        current = ex.scene.entities.get(self.parent.id, self.parent)
        after = ex.scene.measure_fixture_endpoint(current, self.phrase)
        verified, evidence = measure_public_drawer_endpoint(self.before, after, self.mode)
        record = {"version": VERSION, "chunk": chunks, "phase": phase,
                  "verified": verified, "measurement": after, "evidence": evidence,
                  "source": "current_rgbd_and_robot_proprioception",
                  "public_frame": self.public_frame(), "measured_bounds": self.bounds,
                  "before_public_frame": self.before_public_frame,
                  "stop_admitted": False}
        self.records.append(record)
        return record

    def observe(self, chunks):
        ex, p = self.executor, self.executor.p
        first = self.capture(chunks, "after_contact_block")
        if first["verified"] is not True:
            return first
        controls = 0
        for _ in range(STABILITY_CONTROLS):
            if p.env.terminated or p.env.truncated:
                break
            # No release, retreat, wrist movement, or another policy block.
            # Zero delta keeps the gripper actuator's current target.
            p._step_env(np.zeros(7, dtype=np.float32))
            controls += 1
        ex.motion_evidence.append({"name": "drawer_neutral_stability_hold",
            "requested_action_count": STABILITY_CONTROLS, "executed_action_count": controls,
            "steps_used": controls, "actions": [[0.] * 7 for _ in range(controls)],
            "final_eef_pos": p._last_obs_eef_pos.tolist(),
            "gripper_opening": float(p._last_obs_gripper),
            "gripper_command": "preserve_current_actuator_target_zero_delta"})
        second = self.capture(chunks, "after_neutral_stability_hold")
        one, two = first["measurement"], second["measurement"]
        stable, stable_evidence = measure_public_drawer_endpoint(one, two, self.mode)
        ready = (controls == STABILITY_CONTROLS and second["verified"] is True
                 and stable is True and one["source_step"] != two["source_step"])
        if ready:
            delta = np.asarray(two["moving"]["centre"]) - one["moving"]["centre"]
            ready = bool(abs(delta[:2] @ np.asarray(two["outward_axis_xy"])) <= .005)
        second.update(actual_neutral_controls=controls, interval_s=controls * CONTROL_DT_S,
                      gripper_command="preserve_current_actuator_target_zero_delta",
                      stability_evidence=stable_evidence, stop_admitted=bool(ready),
                      stop_reason="measured_drawer_endpoint_hold_verified")
        return second


def make_drawer_endpoint_hold(executor, parent, phrase, mode, before):
    observer = DrawerEndpointHold(executor, parent, phrase, mode, before)
    return observer.observe, observer.records
