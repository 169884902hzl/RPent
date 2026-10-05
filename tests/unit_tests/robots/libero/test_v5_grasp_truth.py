"""Sustained private contact truth, independently of the visual verifier."""

from robots.libero.v5_grasp_truth import sustained_grasp


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
