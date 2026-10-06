"""Occluded placement gets a real view change without fabricated evidence."""

from dataclasses import replace

import numpy as np
import pytest

from robots.libero.v5_runtime import WaypointNotReached
from robots.libero.v5_state import serialize
from tests.unit_tests.robots.libero.test_v5_subtask_release_reverify import run_transfer, transfer


def observed_transfer(monkeypatch, *, enabled=True, frame_defect=None, motion_failure=False,
                      relation="in", opening=.08):
    def frame_change(frame, step, scene):
        if not getattr(scene, "arm_withdrawn", False):
            return replace(frame, visible=False, source_step=1, geometry="cached_perception")
        if frame_defect == "missing":
            return None
        if frame_defect == "occluded":
            return replace(frame, visible=False)
        if frame_defect == "stale":
            return replace(frame, source_step=1)
        if frame_defect == "duplicate":
            return replace(frame, source_step=4)
        if frame_defect == "unstable" and step == 5:
            return replace(frame, xyz=(.04, 0., 1.04))
        if frame_defect == "outside":
            return replace(frame, xyz=(.3, 0., 1.04))
        return frame

    executor, action, calls = transfer(monkeypatch, enabled=False, openings=(opening,),
                                      relation=relation, frame_change=frame_change)
    executor.subtask_place_remeasure_v7 = True
    executor.subtask_place_observe_retreat_v9 = enabled
    executor.drawer_public_stop_v6 = False
    executor.view_retreat_v2 = True
    executor.view_retreat_pose = np.asarray([.4, .4, 1.5])
    executor.retreat_clearance_v1 = False
    calls["moves"] = []

    def move(xyz, gripper):
        calls["moves"].append({"xyz": list(xyz), "gripper": gripper})
        if motion_failure:
            raise WaypointNotReached("servo did not reach measured waypoint")
        executor.p._last_obs_eef_pos = np.asarray(xyz)
        executor.scene.arm_withdrawn = True
        return {"final_dist_m": 0.}

    executor.move = move
    return executor, action, calls


def test_disabled_retains_missing_frame_verdict_and_does_not_move(monkeypatch):
    executor, action, calls = observed_transfer(monkeypatch, enabled=False)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is None
    assert calls["moves"] == [] and calls["release"] == 0
    assert "observation_retreat" not in executor.last_verification_measurements


@pytest.mark.parametrize("relation", ["on", "in"])
def test_real_retreat_keeps_gripper_and_requires_two_new_frames(monkeypatch, relation):
    executor, action, calls = observed_transfer(monkeypatch, relation=relation)
    receipt = run_transfer(executor, action)
    evidence = executor.last_verification_measurements
    assert receipt["place_verified"] is True
    assert calls["moves"] == [{"xyz": [.4, .4, 1.5], "gripper": 0}]
    assert calls["release"] == 0
    assert evidence["opening"] == .08
    assert evidence["first"]["visible"] and evidence["second"]["visible"]
    assert evidence["first"]["source_step"] == 4 < evidence["second"]["source_step"] == 5
    assert evidence["interval_s"] >= .3
    assert evidence["observation_retreat"]["executed"]
    assert evidence["observation_retreat"]["fresh_frames"]
    assert evidence["observation_retreat"]["before_opening_m"] == evidence["observation_retreat"]["after_opening_m"]
    assert "observation_retreat" not in receipt


@pytest.mark.parametrize("defect", ["missing", "occluded", "stale", "duplicate"])
def test_absent_or_reused_evidence_after_real_retreat_remains_null(monkeypatch, defect):
    executor, action, calls = observed_transfer(monkeypatch, frame_defect=defect)
    receipt = run_transfer(executor, action)
    assert len(calls["moves"]) == 1
    assert receipt["place_verified"] is None
    assert receipt["verification_reason"] == "two_frame_evidence_missing"
    assert not executor.last_verification_measurements["observation_retreat"]["fresh_frames"]


@pytest.mark.parametrize("defect", ["unstable", "outside"])
def test_new_frames_still_apply_original_strict_geometry(monkeypatch, defect):
    executor, action, _ = observed_transfer(monkeypatch, frame_defect=defect)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is False
    assert executor.last_verification_measurements["observation_retreat"]["fresh_frames"]


def test_closed_actual_fingers_are_not_replaced_by_opening_assumption(monkeypatch):
    executor, action, calls = observed_transfer(monkeypatch, opening=.03)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is False
    assert calls["release"] == 0 and calls["moves"][0]["gripper"] == 0
    assert executor.last_verification_measurements["opening"] == .03


def test_failed_retreat_never_relabels_missing_evidence(monkeypatch):
    executor, action, calls = observed_transfer(monkeypatch, motion_failure=True)
    receipt = run_transfer(executor, action)
    assert len(calls["moves"]) == 1 and calls["release"] == 0
    assert receipt["place_verified"] is None
    assert executor.last_verification_measurements["observation_retreat"]["failure_reason"] == "observation_retreat_not_reached"


def test_no_retreat_for_already_visible_measurement(monkeypatch):
    executor, action, calls = transfer(monkeypatch, enabled=False, openings=(.08,))
    executor.drawer_public_stop_v6 = False
    executor.subtask_place_observe_retreat_v9 = True
    executor.retreat = lambda: pytest.fail("visible placement must not add a view move")
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is True
    assert "observation_retreat" not in executor.last_verification_measurements


def test_default_off_does_not_change_state_bytes(monkeypatch):
    texts = []
    for explicit_false in (False, True):
        executor, action, _ = transfer(monkeypatch, enabled=False, openings=(.08,))
        executor.drawer_public_stop_v6 = False
        if explicit_false:
            executor.subtask_place_observe_retreat_v9 = False
        receipt = run_transfer(executor, action)
        texts.append(serialize("put the butter in the basket", list(executor.scene.entities.values()),
                               executor.p._last_obs_gripper, executor.held, [receipt]))
    assert texts[0].encode() == texts[1].encode()
