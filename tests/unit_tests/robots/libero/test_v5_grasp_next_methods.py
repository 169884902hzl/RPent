# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Original subtask prompts and two-capture pan measurement contracts."""

from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_state import Entity
from scripts import probe_v5_grasp449_20261005 as probe


def test_full_subtask_bypasses_grasp_prompt_override_without_grasp_stop_object():
    condition = {"profile": "high_short", "contact_execution": "original_subtask"}
    prompt, detail = probe.probe_contact_prompt(
        condition, {"instruction": "put the moka pot on the stove"},
        "put the moka pot on the stove", None, "pick up the frying pan")
    assert prompt is None
    assert detail["full_prompt_origin"] == "original_BDDL_complete_task_sentence"


def test_original_full_subtask_preserves_sentence_and_private_official_metric(monkeypatch):
    from robots.libero.v5_runtime import V5Executor

    calls, replies = [], iter([{"done": False}, {"done": True}])
    client = SimpleNamespace(call=lambda *a, **kw: next(replies))
    executor = SimpleNamespace(p=SimpleNamespace(env=SimpleNamespace(_client=client)),
                               _refresh=lambda names: None, verify_grasp_measurement=lambda obj: False)
    monkeypatch.setattr(V5Executor, "vla_act", lambda self, prompt, budget, stop:
                        calls.append((prompt, budget, stop)) or {"executed": True, "chunks": 3})
    receipt, evidence = {}, {}
    case = {"original_goal_source": True, "instruction": "put the moka pot on the stove"}
    condition = {"max_chunks": 320, "overrides": {"native_grasp_stop_v1": True}}
    probe.execute_original_subtask(executor, case, condition, SimpleNamespace(name="moka pot"), receipt, evidence)
    assert calls == [(case["instruction"], 320, "chunk_budget")]
    assert evidence["private_original_task_status_after"]["done"] is True
    assert receipt["grasp_verified"] is False
    assert "done" not in receipt and "official_subtask_success" not in receipt
    condition["overrides"]["native_grasp_stop_v1"] = False
    with pytest.raises(ValueError, match="native termination"):
        probe.execute_original_subtask(executor, case, condition, SimpleNamespace(name="moka pot"), {}, {})


@pytest.mark.parametrize("visible", [True, False])
def test_pan_verifier_uses_two_fresh_captures_and_public_hold(monkeypatch, visible):
    from robots.libero import v5_perception_geometry

    calls = []
    before = Entity("e1", "frypan", (0, 0, .04), (-.04, -.02, 0), (.04, .02, .08), source_step=0)
    state = SimpleNamespace(latest_step=0, load=lambda *a, **kw: np.zeros((2, 2, 3)))
    scene = SimpleNamespace(entities={"e1": before}, measurement_views={}, measurement_clouds_by_view={})
    raw = {"robot0_eef_pos": [0, 0, .1], "robot0_eef_quat": [0, 0, 0, 1],
           "robot0_gripper_qpos": [.02, -.02]}
    primitive = SimpleNamespace(env=SimpleNamespace(terminated=False, truncated=False, raw_obs=lambda: raw),
        _last_obs_gripper=.04, _last_obs_eef_pos=np.asarray([0., 0., .05]),
        pi0_pick=lambda prompt, max_chunks: calls.append(("pick", prompt, max_chunks)) or {"chunks_used": 2},
        set_gripper=lambda **kw: calls.append(("hold", kw)))
    calibration = {"opening_calibration": {"closed_empty_max_m": .003, "open_empty_min_m": .078,
        "max_sensor_opening_m": .081, "tolerance_m": .002, "minimum_points_per_finger": None},
        "grip_site_geometry": {"rotation_body_to_site": np.eye(3).tolist(),
            "finger_centre_offset_from_site_m": [0, 0, 0], "closing_axis": 0,
            "pad_depth_half_m": .03, "pad_height_half_m": .03},
        "robot_rigid_transform_validation": "synthetic_unit_fixture_only"}

    def refresh(names):
        state.latest_step += 1
        calls.append(("capture", state.latest_step))
        current = Entity("e1", "frypan", (0, 0, .12), (-.04, -.02, .08), (.04, .02, .16),
                         source_step=state.latest_step, visible=visible)
        scene.entities = {"e1": current}
        scene.measurement_views = {"e1": {"agentview": current, "wrist": current}}

    executor = SimpleNamespace(p=primitive, toolkit=SimpleNamespace(_state=state), scene=scene,
        grasp_measurement_calibration=calibration, opening_may_hold=lambda opening: True,
        move=lambda *a, **kw: {"waypoint_reached": True}, _refresh=refresh)
    monkeypatch.setattr(v5_perception_geometry, "measured_work_surface", lambda *a: {"height_m": 0})
    monkeypatch.setattr(probe, "measured_pan_handle_views", lambda *a: ({}, {}))
    evidence = {}
    receipt = probe.rpent_pick_then_independent_handle_measure(executor, "pick up the frying pan", 320,
        before, trial_lift_m=.1, evidence=evidence)
    assert calls == [("pick", "pick up the frying pan", 320), ("capture", 1),
                     ("hold", {"gripper": 1, "steps": 10}), ("capture", 2)]
    assert receipt["grasp_verified"] is (True if visible else None)
    assert len(evidence["stable_visual_grasp"]["frames"]) == 2
    assert evidence["stable_visual_grasp"]["paired_verdict"]["interval_s"] == .5
