"""A release history requests a real opening, never replaces current sensors."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity, serialize


def transfer(monkeypatch, *, enabled=True, openings=(.08, .025), release_opening=.08,
             relation="on", frame_change=None, eef=(.3, .3, 1.4)):
    clock = [0.]
    monkeypatch.setattr("robots.libero.v5_runtime.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr("robots.libero.v5_runtime.time.sleep", lambda elapsed: clock.__setitem__(0, clock[0] + elapsed))
    obj = Entity("e1", "butter", (0., 0., 1.04), (-.02, -.02, 1.02), (.02, .02, 1.06), source_step=1)
    target = Entity("e2", "plate" if relation == "on" else "basket", (0., 0., 1.),
                    (-.1, -.1, .9), (.1, .1, 1.02 if relation == "on" else 1.2), source_step=1)
    scene = SimpleNamespace(entities={obj.id: obj, target.id: target},
        last_measurement_s={obj.name: 0.}, view_axes=((1., 0., 0.), (0., -1., 0.)))
    calls = {"refresh": [], "release": 0, "captures": 0}
    p = SimpleNamespace(_last_obs_gripper=.03, _last_obs_eef_pos=np.asarray(eef),
                        env=SimpleNamespace(terminated=False, truncated=False))
    chunks = iter(openings)
    def chunk(_prompt):
        p._last_obs_gripper = next(chunks)
    def release():
        calls["release"] += 1
        p._last_obs_gripper = release_opening
        return {"name": "release", "final_gripper_opening": release_opening}
    p._vlm_chunk, p.release = chunk, release
    def refresh(names, **kwargs):
        calls["refresh"].append(kwargs)
        step = 1 + len(calls["refresh"])
        current = replace(obj, source_step=step)
        if frame_change is not None:
            current = frame_change(current, step, scene)
        if current is None:
            scene.entities.pop(obj.id, None)
        else:
            scene.entities[obj.id] = current
        scene.last_measurement_s[obj.name] = clock[0]
    scene.refresh = refresh
    executor = V5Executor.__new__(V5Executor)
    executor.scene, executor.p = scene, p
    executor.target_cache_v1 = True
    executor.target_cache = {}
    executor.strict_place_v6 = True
    executor.subtask_release_reverify_v8 = enabled
    executor.max_chunks = len(openings)
    executor.motion_trace_v1 = False
    executor.motion_evidence = []
    executor.held, executor.held_offset = obj.id, np.zeros(3)
    executor._refresh = refresh
    def capture():
        calls["captures"] += 1
    executor.capture = capture
    return executor, Candidate("vla_subtask", obj.id, target.id, relation), calls


def run_transfer(executor, action):
    receipt = {}
    executor.execute_subtask(action, receipt)
    return receipt


def test_default_off_does_not_open_or_add_public_or_diagnostic_fields(monkeypatch):
    executor, action, calls = transfer(monkeypatch, enabled=False)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is False
    assert calls["release"] == 0
    assert "release_reverification" not in executor.last_verification_measurements
    assert not hasattr(executor, "last_vla_release_evidence")


@pytest.mark.parametrize("relation", ["on", "in"])
def test_same_action_opening_then_closure_uses_actual_release_and_new_frames(monkeypatch, relation):
    executor, action, calls = transfer(monkeypatch, relation=relation)
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is True
    assert calls["release"] == 1
    evidence = executor.last_verification_measurements
    trace = evidence["release_reverification"]
    assert trace["triggered"] and trace["fresh_after_release"]
    assert trace["before"]["opening_m"] == .025
    assert evidence["opening"] == .08
    assert evidence["first"]["source_step"] == 4
    assert evidence["second"]["source_step"] == 5
    assert executor.held is executor.held_offset is None
    sensors = trace["release_history"]
    assert sensors["open_events"] == [0]
    assert sensors["chunks"][1] == {
        "chunk": 1, "opening_before_m": .08, "opening_after_m": .025,
        "eef_xyz": [.3, .3, 1.4], "source": "same_vla_action_proprioception"}
    assert "release_history" not in receipt and "release_reverification" not in receipt
    assert len(executor.motion_evidence) == 1


def test_old_action_release_history_cannot_authorize_opening(monkeypatch):
    executor, action, calls = transfer(monkeypatch, openings=(.025, .03))
    executor.last_vla_release_evidence = {"open_events": [0], "prompt_sha256": "old"}
    receipt = run_transfer(executor, action)
    assert receipt["place_verified"] is False
    assert calls["release"] == 0
    assert executor.last_verification_measurements["release_reverification"]["release_history"]["open_events"] == []


def test_diagnostic_sensors_do_not_add_state_text(monkeypatch):
    texts = []
    for enabled in (False, True):
        executor, action, _ = transfer(monkeypatch, enabled=enabled, openings=(.025, .03))
        receipt = run_transfer(executor, action)
        texts.append(serialize("move the butter", list(executor.scene.entities.values()),
                               executor.p._last_obs_gripper, executor.held, [receipt]))
    assert texts[0].encode() == texts[1].encode()
    assert "same_vla_action" not in texts[1] and "release_reverif" not in texts[1]


@pytest.mark.parametrize("release_opening", [.03, .069, .071])
def test_verdict_uses_real_opening_after_command(monkeypatch, release_opening):
    executor, action, calls = transfer(monkeypatch, release_opening=release_opening)
    receipt = run_transfer(executor, action)
    assert calls["release"] == 1
    assert receipt["place_verified"] is (release_opening >= .07)
    assert executor.last_verification_measurements["opening"] == release_opening
    if release_opening >= .07:
        assert executor.held is None


@pytest.mark.parametrize("bad_frame", ["missing", "occluded", "stale", "duplicate"])
def test_missing_or_stale_new_evidence_remains_unknown(monkeypatch, bad_frame):
    def change(frame, step, _scene):
        if step < 4:
            return frame
        if bad_frame == "missing":
            return None
        if bad_frame == "occluded":
            return replace(frame, visible=False, geometry="cached_perception")
        return replace(frame, source_step=3 if bad_frame == "stale" else 4)
    executor, action, calls = transfer(monkeypatch, frame_change=change)
    receipt = run_transfer(executor, action)
    assert calls["release"] == 1
    assert receipt["place_verified"] is None
    assert receipt["verification_reason"] == "two_frame_evidence_missing"


@pytest.mark.parametrize("defect", ["occluded", "stale", "duplicate", "unstable",
    "outside_xy", "outside_z", "footprint", "support_gap", "region", "shell", "floor"])
def test_failed_strict_geometry_never_commands_release(monkeypatch, defect):
    relation = "in" if defect in ("shell", "floor") else "on"
    def change(frame, step, scene):
        if defect == "occluded":
            return replace(frame, visible=False)
        if defect == "stale":
            return replace(frame, source_step=1)
        if defect == "duplicate":
            return replace(frame, source_step=2)
        if defect == "unstable" and step == 3:
            return replace(frame, xyz=(.03, 0., 1.04))
        if defect == "outside_xy":
            return replace(frame, xyz=(.2, 0., 1.04))
        if defect == "outside_z":
            return replace(frame, xyz=(0., 0., 1.01))
        if defect == "footprint":
            scene.entities["e2"] = replace(scene.entities["e2"], lower=(-.017, -.1, .9), upper=(.017, .1, 1.02))
        if defect == "support_gap":
            return replace(frame, lower=(-.02, -.02, 1.031))
        if defect == "floor":
            return replace(frame, lower=(-.02, -.02, .88))
        return frame
    executor, action, calls = transfer(monkeypatch, relation=relation, frame_change=change)
    if defect == "region":
        executor.scene.entities["e2"] = replace(executor.scene.entities["e2"], name="area left")
    if defect == "shell":
        executor.scene.entities["e2"] = replace(executor.scene.entities["e2"], name="microwave", geometry="measured_front_surface")
    # These faults must already be in the cached pre-action target.
    if defect == "footprint":
        executor.scene.entities["e2"] = replace(executor.scene.entities["e2"], lower=(-.017, -.1, .9), upper=(.017, .1, 1.02))
    run_transfer(executor, action)
    assert calls["release"] == 0
    assert executor.last_verification_measurements["release_reverification"]["geometry_passed"] is False


def test_not_withdrawn_never_commands_release(monkeypatch):
    executor, action, calls = transfer(monkeypatch, eef=(0., 0., 1.07))
    run_transfer(executor, action)
    assert calls["release"] == 0


def test_in_footprint_threshold_is_not_relaxed(monkeypatch):
    executor, action, calls = transfer(monkeypatch, relation="in")
    target = executor.scene.entities["e2"]
    executor.scene.entities["e2"] = replace(target, lower=(-.016, -.1, .9), upper=(.016, .1, 1.2))
    run_transfer(executor, action)
    assert calls["release"] == 0


def test_released_object_can_fail_new_geometry(monkeypatch):
    def change(frame, step, _scene):
        return replace(frame, xyz=(.2, 0., 1.04)) if step >= 4 else frame
    executor, action, calls = transfer(monkeypatch, frame_change=change)
    receipt = run_transfer(executor, action)
    assert calls["release"] == 1
    assert receipt["place_verified"] is False
