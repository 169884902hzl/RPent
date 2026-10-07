"""A fresh public endpoint pauses contact instead of running another block."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_drawer_endpoint_hold import (
    DrawerEndpointHold, measure_public_drawer_endpoint,
)
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity


def frame(extension, step):
    return {"source": "perception", "source_step": step,
            "anchor_parent": "e1", "anchor_part": "e2", "current_part": "e2",
            "current_part_source_step": step, "outward_axis_xy": [0., 1.],
            "frame": {"centre": [0., 0., 1.], "normal_xy": [0., 1.]},
            "moving": {"centre": [0., extension, 1.], "normal_xy": [0., 1.]}}


def executor_for(monkeypatch, frames):
    parent = Entity("e1", "cabinet", (0., 0., 1.), (-.1, -.1, .9), (.1, .1, 1.2))
    iterator = iter(deepcopy(frames))
    state = SimpleNamespace(latest_step=0)
    controls, contacts = [], []
    p = SimpleNamespace(_last_obs_gripper=.04, _last_obs_eef_pos=np.array([0., 0., 1.]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    p._step_env = lambda action: controls.append(np.array(action, copy=True))
    p._vlm_chunk = lambda prompt: contacts.append(prompt)

    def prohibited(*args, **kwargs):
        pytest.fail("endpoint hold must not release, retreat, or read private labels")

    p.release = prohibited
    scene = SimpleNamespace(entities={parent.id: parent})

    def measured(*args):
        sample = next(iterator)
        state.latest_step = sample["source_step"]
        return sample

    scene.measure_fixture_endpoint = measured
    toolkit = SimpleNamespace(primitives=p, _state=state)
    executor = V5Executor(toolkit, scene, drawer_public_stop_v6=True, drawer_endpoint_hold_v9=True)
    executor._refresh = lambda names: None
    executor.retreat = prohibited
    monkeypatch.setattr("robots.libero.v5_temporal_verifier.public_frame",
        lambda ex, bounds, **kwargs: {"source_step": state.latest_step, "views": {},
            "public_robot_observation": {"eef_xyz_m": [0., 0., 1.], "gripper_opening_m": .04},
            "private_object_or_joint_values": False, "features": np.zeros(1)})
    return executor, parent, controls, contacts


def test_first_endpoint_holds_without_another_policy_block_or_gripper_change(monkeypatch):
    executor, parent, controls, contacts = executor_for(monkeypatch, [frame(.15, 1), frame(.1502, 2)])
    callback = executor.drawer_public_stop(parent, "top drawer", "open", frame(0., 0))
    result = executor.vla_act("open the top drawer", 160, "chunk_budget", public_stop=callback)
    assert len(contacts) == 1
    assert len(controls) == 6 and np.array_equal(np.stack(controls), np.zeros((6, 7)))
    assert executor.p._last_obs_gripper == .04
    assert result["chunks"] == 1
    assert result["stop"] == "measured_drawer_endpoint_hold_verified"
    assert executor.motion_evidence[-1]["executed_action_count"] == 6
    assert result["temporal_endpoint"]["interval_s"] == pytest.approx(.3)
    assert [sample["phase"] for sample in executor.last_verification_measurements["drawer_public_stop"]] == [
        "after_contact_block", "after_neutral_stability_hold"]


@pytest.mark.parametrize("second", [frame(.15, 1), frame(.10, 2),
    {**frame(.15, 2), "moving": None}, {**frame(.15, 2), "source": "sim_truth"}])
def test_stale_lost_or_nonpublic_second_frame_cannot_admit_stop(monkeypatch, second):
    executor, parent, controls, _ = executor_for(monkeypatch, [frame(.15, 1), second])
    observer = DrawerEndpointHold(executor, parent, "top drawer", "open", frame(0., 0))
    evidence = observer.observe(1)
    assert len(controls) == 6
    assert evidence["stop_admitted"] is False


def test_unqualified_close_identity_is_unknown_even_when_geometry_says_closed(monkeypatch):
    executor, parent, controls, _ = executor_for(monkeypatch, [frame(-.009, 1)])
    observer = DrawerEndpointHold(executor, parent, "bottom drawer", "close", frame(.157, 0))
    evidence = observer.observe(1)
    assert evidence["verified"] is None and evidence["stop_admitted"] is False
    assert evidence["evidence"]["geometric_endpoint_candidate"] is True
    assert evidence["evidence"]["reason"] == "drawer_close_face_identity_not_qualified"
    assert controls == []


def test_final_receipt_admission_uses_same_public_identity_rule():
    verdict, evidence = measure_public_drawer_endpoint(frame(.157, 0), frame(-.009, 3), "close")
    assert verdict is None
    assert evidence["close_verifier_qualification"] == "not_passed"


def test_incomplete_neutral_hold_cannot_admit_stop(monkeypatch):
    executor, parent, controls, _ = executor_for(monkeypatch, [frame(.15, 1), frame(.15, 2)])
    def step(action):
        controls.append(np.array(action, copy=True))
        executor.p.env.truncated = True
    executor.p._step_env = step
    observer = DrawerEndpointHold(executor, parent, "top drawer", "open", frame(0., 0))
    assert observer.observe(1)["stop_admitted"] is False
    assert len(controls) == 1
