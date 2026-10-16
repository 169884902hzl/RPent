"""Public-only skill request and exact-ID execution checks."""
from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_state import Entity
from rpent.skill_package.contract import selected
from tests.unit_tests.robots.libero.test_bounded_motion import FakePrimitives


@pytest.fixture
def adapter(monkeypatch):
    p = FakePrimitives()
    p.env.execution_budget = lambda: {"remaining_sim_steps": 10000-len(p.actions), "used_sim_steps": len(p.actions)}
    entity = Entity("e1", "box", (.1, .1, .9), (.08, .08, .88), (.12, .12, .92), True, 0)
    scene = SimpleNamespace(entities={"e1": entity}, vocabulary={"box"}, refresh=lambda names: None,
        _scores={"e1": .9}, dual_view_fusion_v1=True, view_axes=((1, 0, 0), (0, -1, 0)), measurement_clouds={})
    geometry = {"boxes": [], "max_opening_m": .08}
    monkeypatch.setattr("robots.libero.bounded_skills.panda_geometry", lambda xml: geometry)
    ex = SimpleNamespace(p=p, scene=scene, instruction="put the box on the plate", capture=lambda: None, held=None)
    result = MeasuredSkillAdapter(ex, "/static/grippers/panda_gripper.xml", allow_vla=False)
    result.grasp_geometry = lambda e: {"xyz_m": [.1, .1, .9], "quat_xyzw": [0, 0, 0, 1], "width_m": .04}
    result._cloud_and_ik = lambda *args, **kwargs: lambda poses: {
        "passed": True, "reason": "test_public_geometry", "collision": False, "ik_reachable": True,
        "path_min_clearance_m": .05, "screen_scope": "test_measured_mesh"}
    return result


def decision(request, ids):
    return {"schema_version": request["schema_version"], "kind": "decision", "revision": request["revision"],
            "observation_id": request["observation_id"], "candidate_ids": ids}


def test_public_request_omits_whole_task_and_vla_disabled(adapter):
    request = adapter.request(k=4)
    assert not any(c["skill"] in {"vla_task", "call_vla"} for c in request["candidates"])
    assert len([c for c in request["candidates"] if c["skill"] == "move_to"]) == 12
    with pytest.raises(ValueError, match="unknown"):
        selected(request, decision(request, ["invented"]))
    with pytest.raises(ValueError, match="stale"):
        selected(request, {**decision(request, [request["candidates"][0]["id"]]), "revision": 100})


def test_motion_candidate_executes_using_measured_pose(adapter):
    request = adapter.request(k=1)
    candidate = next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": "x", "distance_m": .01})
    receipt = adapter.execute(request, decision(request, [candidate["id"]]))[0]
    assert receipt["outcome"] == "success"
    assert receipt["steps_used"] > 0
    assert abs(receipt["after"]["eef_xyz_m"][0]-.01) < 1e-8


def test_contact_boundary_cannot_have_hidden_suffix(adapter):
    request = adapter.request(k=4)
    close = next(c for c in request["candidates"] if c["skill"] == "set_gripper" and c["parameters"]["mode"] == "close")
    observe = next(c for c in request["candidates"] if c["skill"] == "observe")
    with pytest.raises(ValueError, match="boundary"):
        selected(request, decision(request, [close["id"], observe["id"]]))


def test_k4_motion_prefix_is_actually_blended(adapter):
    request = adapter.request(k=4)
    moves = [next(c for c in request["candidates"] if c["skill"] == "nudge" and c["parameters"] == {"axis": axis, "distance_m": .01}) for axis in ("x", "y")]
    adapter.execute(request, decision(request, [c["id"] for c in moves]))
    assert adapter.details[-1]["blended"]
    assert len(adapter.details[-1]["candidate_ids"]) == 2
    np.testing.assert_allclose(adapter.robot()["eef_xyz_m"], [.01, .01, 1.], atol=1e-8)
