"""Sustained private contact truth, independently of the visual verifier."""

from types import SimpleNamespace

import pytest

from robots.libero.v5_grasp_truth import contact_sample, sustained_grasp


REFERENCE = {"lower_extent_m": .8, "other_contact_geoms": ["table"]}


def sample(time, height=.85, contact=True, supports=()):
    return {"sim_time": time, "lower_extent_m": height, "finger_contact": contact,
            "dual_finger_contact": False, "other_contact_geoms": list(supports)}


def test_single_finger_handle_support_can_be_true_without_opposing_pad_predicate():
    result = sustained_grasp([sample(t) for t in (0, .1, .3, .5)], REFERENCE)
    assert result["success"]


def test_lifted_but_not_held_object_is_false():
    assert not sustained_grasp([sample(0, contact=False), sample(.5, contact=False)], REFERENCE)["success"]


def test_transient_lift_or_slip_does_not_count_as_sustained_grasp():
    assert not sustained_grasp([sample(0), sample(.3)], REFERENCE)["success"]
    assert not sustained_grasp([sample(0), sample(.3, height=.81), sample(.5)], REFERENCE)["success"]
    assert not sustained_grasp([sample(0), sample(.2, contact=False), sample(.5)], REFERENCE)["success"]


def test_original_support_contact_rejects_lift_that_remains_propped():
    assert not sustained_grasp([sample(0), sample(.5, supports=("table",))], REFERENCE)["success"]


@pytest.mark.parametrize("composite", [False, True])
def test_real_robosuite_gripper_mapping_preserves_finger_contact(monkeypatch, composite):
    import robots.libero.v5_grasp_truth as truth

    component = SimpleNamespace(important_geoms={"left_fingerpad": ["pad"], "palm": ["palm"]})
    gripper = {"right": component} if composite else component
    names = ["target", "pad", "table"]
    data = SimpleNamespace(time=1., ncon=2, contact=[
        SimpleNamespace(geom1=0, geom2=1, dist=-.001),
        SimpleNamespace(geom1=0, geom2=2, dist=-.001)])
    env = SimpleNamespace(objects_dict={"obj": SimpleNamespace(contact_geoms=["target"])},
                          sim=SimpleNamespace(model=SimpleNamespace(geom_id2name=lambda i: names[i]), data=data),
                          robots=[SimpleNamespace(gripper=gripper)], _check_grasp=lambda *args: False)
    monkeypatch.setattr(truth, "object_lower_extent", lambda *args: .85)
    measured = contact_sample(env, "obj")
    assert measured["finger_contact"] is True
    assert measured["finger_geoms"] == ["pad"]
    assert measured["other_contact_geoms"] == ["table"]
    assert measured["dual_finger_contact"] is False
