# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Stop a placement macro only at a fresh, released public strict6 endpoint.

The contact policy must open its own gripper and withdraw on its own. This
callback does not release, retreat, move, query oracle status or inspect native
goal latches. Its only added controls are a neutral stability hold after an
actually open gripper, followed by a second current dual-view measurement.
"""

from __future__ import annotations

import copy
import math
import time

import numpy as np

from robots.libero.v5_public_fixture_identity import placement_target_moves
from robots.libero.v5_state import Entity, entity_record
from robots.libero.v5_verification import strict_place_verified_v6


VERSION = "public-placement-strict6-endpoint-stop/1-dev"
CONTROL_DT_S = .05
STABILITY_CONTROLS = 6


def measure_placement_endpoint(first, second, target: Entity, relation: str, *,
                               baseline_step: int, actual_hold_controls: int,
                               control_dt_s: float = CONTROL_DT_S) -> dict:
    """Judge explicit public samples; missing or stale observations stay null."""
    evidence = {"version": VERSION, "source": "perception", "relation": relation,
                "target": entity_record(target), "target_binding": "stationary_public_measurement_cached_before_contact",
                "first": first, "second": second, "baseline_step": baseline_step,
                "actual_hold_controls": actual_hold_controls, "control_dt_s": control_dt_s,
                "interval_s": actual_hold_controls * control_dt_s,
                "place_verified": None, "stop_admitted": False, "status": "unmeasured",
                "stop_reason": "placement_endpoint_verified"}

    def unknown(reason):
        return {**evidence, "reason": reason}

    if relation not in ("on", "in") or placement_target_moves(target) or not target.visible:
        return unknown("stationary_measured_target_required")
    if (type(actual_hold_controls) is not int or actual_hold_controls < 0
            or not math.isfinite(control_dt_s) or control_dt_s <= 0
            or actual_hold_controls * control_dt_s < .3 - 1e-9):
        return unknown("physical_stability_interval_incomplete")
    entities, sensors = [], []
    for frame in (first, second):
        if not isinstance(frame, dict) or frame.get("source") != "perception":
            return unknown("public_frame_source_missing")
        measured = frame.get("entity")
        capture_step = frame.get("capture_step")
        if (not isinstance(measured, Entity) or not measured.visible
                or type(capture_step) is not int or measured.source_step != capture_step):
            return unknown("current_visible_object_measurement_missing")
        try:
            opening = float(frame["opening_m"])
            eef = tuple(map(float, frame["eef_xyz_m"]))
        except (KeyError, TypeError, ValueError):
            return unknown("public_robot_measurement_missing")
        if len(eef) != 3 or not all(math.isfinite(value) for value in (*eef, opening)):
            return unknown("public_robot_measurement_invalid")
        entities.append(measured)
        sensors.append((opening, eef))
    if (entities[0].id != entities[1].id or not baseline_step < entities[0].source_step < entities[1].source_step
            or target.source_step > baseline_step):
        return unknown("two_fresh_distinct_object_frames_required")
    # strict6 receives the actual physical hold interval and both frames' actual
    # robot sensors. Opening or withdrawal at only one end cannot admit stop.
    verdicts = [strict_place_verified_v6(entities[0], entities[1], target,
                opening, eef, evidence["interval_s"], relation=relation) for opening, eef in sensors]
    if any(verdict is None for verdict in verdicts):
        return unknown("strict6_support_or_containment_unmeasured")
    verified = all(verdict is True for verdict in verdicts)
    evidence.update(status="measured", place_verified=bool(verified), stop_admitted=bool(verified),
                    strict6_verdicts=verdicts,
                    reason="fresh_strict6_endpoint" if verified else "strict6_endpoint_not_verified")
    return evidence


def _serializable_evidence(evidence):
    """Preserve Entity provenance without putting a Python object in the ledger."""
    result = copy.deepcopy(evidence)
    for phase in ("first", "second"):
        frame = result.get(phase)
        if isinstance(frame, dict) and isinstance(frame.get("entity"), Entity):
            frame["entity"] = entity_record(frame["entity"])
    return result


class PlacementEndpointStop:
    """Bound the public probe after a placement macro has opened its gripper."""

    def __init__(self, executor, obj: Entity, target: Entity, relation: str):
        if relation not in ("on", "in") or placement_target_moves(target) or obj.id == target.id:
            raise ValueError("placement stop requires distinct object and stationary on/in target")
        self.executor, self.obj, self.target, self.relation = executor, obj, target, relation
        self.baseline_step = executor.toolkit._state.latest_step
        self.records = []
        self.frames = []

    def capture(self):
        ex = self.executor
        ex.capture(sync_robot=True)
        timestamp = time.monotonic()
        # Main view is primary so a wrist near a placed coffee pot cannot turn
        # an otherwise visible body into a rim-only cached measurement.
        ex.scene.refresh([self.obj.name], placement=(self.obj, self.target), camera_view="agentview")
        frame = {"source": "perception", "capture_step": ex.toolkit._state.latest_step,
                "capture_wall_timestamp_s": timestamp,
                "entity": ex.scene.entities.get(self.obj.id),
                "opening_m": float(ex.p._last_obs_gripper), "eef_xyz_m": ex.p._last_obs_eef_pos.tolist(),
                "primary_camera": "agentview", "fusion_version": "rgbd_dual_view/1",
                "measurement_provenance": copy.deepcopy(ex.scene.perception_evidence.get(self.obj.id, {}))}
        if getattr(ex, "subtask_terminal_measurement_v1", False):
            frame["used_sim_steps"] = ex.p.env.execution_budget()["used_sim_steps"]
            self.frames.append(frame)
            self.frames = self.frames[-4:]
        return frame

    def observe_terminal(self):
        """Measure the stopped scene using earlier public frames; add no controls."""
        previous = list(self.frames)
        second = self.capture()
        eligible = [frame for frame in previous
                    if second["used_sim_steps"] - frame["used_sim_steps"] >= STABILITY_CONTROLS]
        first = eligible[-1] if eligible else None
        controls = second["used_sim_steps"] - first["used_sim_steps"] if first else 0
        evidence = measure_placement_endpoint(first, second, self.target, self.relation,
            baseline_step=self.baseline_step, actual_hold_controls=controls)
        evidence.update(measurement_scope="terminal_read_only_public_frames/1-dev",
                        added_controls=0, interval_source="public_action_counter",
                        interval_controls_kind="policy_controls_between_public_samples",
                        gripper_command="unchanged; read-only terminal measurement")
        if first is None:
            evidence["reason"] = "preterminal_public_stability_frame_missing"
        evidence = _serializable_evidence(evidence)
        self.records.append(evidence)
        return evidence

    def observe(self, chunks):
        ex, p = self.executor, self.executor.p
        opening = float(p._last_obs_gripper)
        if opening < .07:
            evidence = {"version": VERSION, "source": "robot_proprioception", "chunks": chunks,
                        "opening_m": opening, "status": "not_probed", "stop_admitted": False,
                        "reason": "contact_policy_has_not_opened_gripper"}
            if getattr(ex, "subtask_terminal_measurement_v1", False):
                evidence["public_frame"] = _serializable_evidence({"first": self.capture()})["first"]
            self.records.append(evidence)
            return evidence
        if not ex.scene.dual_view_fusion_v1:
            evidence = {"version": VERSION, "status": "unmeasured", "chunks": chunks,
                        "stop_admitted": False, "reason": "dual_view_fusion_not_enabled"}
            self.records.append(evidence)
            return evidence
        first = self.capture()
        controls = 0
        for _ in range(STABILITY_CONTROLS):
            if p.env.terminated or p.env.truncated:
                break
            p._step_env(np.zeros(7, dtype=np.float32))
            controls += 1
        second = self.capture()
        evidence = measure_placement_endpoint(first, second, self.target, self.relation,
                        baseline_step=self.baseline_step, actual_hold_controls=controls)
        evidence.update(chunks=chunks,
                        wall_capture_interval_s=second["capture_wall_timestamp_s"] - first["capture_wall_timestamp_s"],
                        gripper_command="no added release; neutral stability hold only")
        evidence = _serializable_evidence(evidence)
        self.records.append(evidence)
        return evidence


def make_placement_public_stop(executor, obj, target, relation):
    collector = PlacementEndpointStop(executor, obj, target, relation)
    return collector.observe, collector.records
