"""Losing a close-up measurement is a recoverable skill result."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Candidate, Entity


def test_closeup_miss_preserves_motion_without_raising_or_running_contact():
    obj = Entity("e1", "moka pot", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    scene = SimpleNamespace(entities={obj.id: obj})
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]),
                        env=SimpleNamespace(terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=p), scene,
                          wrist_refine_v1=True, grasp_safe_approach_v2=True)
    executor.capture = lambda: None
    scene.refresh = lambda *args, **kwargs: scene.entities.update({obj.id: replace(obj, visible=False)})

    def stage(*args, **kwargs):
        executor.motion_evidence.append({"actions_used": 45})
        return True

    executor.stage_grasp = stage
    executor.vla_act = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("contact ran"))
    receipt = {"executed": False}
    executor._execute(Candidate("grasp", obj.id, mode="direct"), receipt, None)
    assert receipt["executed"] is True
    assert receipt["verification"] == "unmeasured"
    assert receipt["grasp_verified"] is None
    assert receipt["failure_reason"] == "grasp_closeup_not_measured"
    assert receipt["recoverable"] is True
    assert "error" not in receipt


@pytest.mark.parametrize("enabled,standoff,tolerance", [(False, .15, .08), (True, .05, .02)])
def test_wrist_refined_contact_descends_at_the_new_measured_position(enabled, standoff, tolerance):
    before = Entity("e1", "box", (0., 0., 1.), (-.03, -.03, .98), (.03, .03, 1.02))
    after = replace(before, xyz=(.06, .04, 1.), lower=(.03, .01, .98),
                    upper=(.09, .07, 1.02), source_step=7)
    scene = SimpleNamespace(entities={before.id: before})
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.3]),
                                _last_obs_gripper=.08,
                                env=SimpleNamespace(terminated=False, truncated=False))
    executor = V5Executor(SimpleNamespace(primitives=primitive), scene,
                          wrist_refine_v1=True, wrist_measurement_standoff_v2=True,
                          grasp_safe_approach_v2=True, grasp_wrist_contact_v3=enabled)
    movements, contact_positions, contact_tolerances, views = [], [], [], []

    def move(target, gripper, **kwargs):
        movements.append((list(target), kwargs))
        primitive._last_obs_eef_pos = np.asarray(target)
        return {"final_dist_m": 0., "waypoint_reached": True}

    def refine(names, **kwargs):
        views.append((kwargs["camera_view"], primitive._last_obs_eef_pos.copy()))
        scene.entities[before.id] = after

    def contact(*args, **kwargs):
        contact_positions.append(primitive._last_obs_eef_pos.copy())
        contact_tolerances.append(movements[-1][1]["tolerance_m"])
        return {"grasp_verified": False, "stop": "chunk_budget"}

    executor.move, executor.vla_act = move, contact
    executor.capture = lambda: None
    executor._refresh = lambda names: None
    scene.refresh = refine
    receipt = {}
    executor._execute(Candidate("grasp", before.id, mode="direct"), receipt, None)
    assert len(views) == 1 and views[0][0] == "wrist"
    assert views[0][1] == pytest.approx([0., 0., before.upper[2] + .15])
    assert len(contact_positions) == 1
    assert contact_positions[0] == pytest.approx([.06, .04, after.upper[2] + standoff])
    assert contact_tolerances == [tolerance]
    assert receipt["contact_policy_standoff_m"] == standoff
    if enabled:
        assert receipt["grasp_contact_handoff"]["measurement_step"] == 7
    else:
        assert "grasp_contact_handoff" not in receipt


def test_precise_near_contact_waypoint_failure_prevents_contact_execution():
    primitive = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]),
                                env=SimpleNamespace(terminated=False, truncated=False),
                                move_to=lambda *args, **kwargs: {"steps_used": 80, "final_dist_m": .03})
    executor = V5Executor(SimpleNamespace(primitives=primitive), SimpleNamespace())
    obj = Entity("e1", "box", (.06, .04, 1.), (.03, .01, .98), (.09, .07, 1.02))
    receipt = {}
    assert not executor.stage_grasp(obj, [.06, .04, 1.07], receipt,
                                    minimum_standoff_m=.05, approach_tolerance_m=.02)
    assert receipt["failure_reason"] == "approach_not_reached"
