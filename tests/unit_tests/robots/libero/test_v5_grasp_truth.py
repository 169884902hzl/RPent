"""Sustained private contact truth, independently of the visual verifier."""

from types import SimpleNamespace

import pytest

from robots.libero.v5_grasp_truth import (GRIPPER_GEOMETRY_SOURCE, GRIPPER_GEOMETRY_VERSION,
                                        SUPPORT_RULE_V2, contact_sample,
                                        grasp_trace_summary_v2, sustained_grasp,
                                        sustained_grasp_v2)


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


def test_unnamed_support_contact_is_preserved_by_geometry_identity(monkeypatch):
    import robots.libero.v5_grasp_truth as truth
    names = ["target", "table", None]
    data = SimpleNamespace(time=1., ncon=2, contact=[
        SimpleNamespace(geom1=0, geom2=1, dist=-.001),
        SimpleNamespace(geom1=0, geom2=2, dist=-.001)])
    gripper = SimpleNamespace(important_geoms={"left_fingerpad": ["pad"]})
    env = SimpleNamespace(objects_dict={"obj": SimpleNamespace(contact_geoms=["target"])},
        sim=SimpleNamespace(model=SimpleNamespace(geom_id2name=lambda i: names[i]), data=data),
        robots=[SimpleNamespace(gripper=gripper)], _check_grasp=lambda *args: False)
    monkeypatch.setattr(truth, "object_lower_extent", lambda *args: .85)
    measured = contact_sample(env, "obj")
    assert measured["other_contact_geoms"] == ["table", "unnamed_geom:2"]
    result = sustained_grasp([sample(0, supports=("unnamed_geom:2",)), sample(.5, supports=("unnamed_geom:2",))],
                            {"lower_extent_m": .8, "other_contact_geoms": ["unnamed_geom:2"]})
    assert not result["success"]


def sample_v2(time, height=.85, contact=True, supports=()):
    return {**sample(time, height, contact, supports),
            "all_non_gripper_contact_geoms": list(supports),
            "gripper_geometry": {"version": GRIPPER_GEOMETRY_VERSION,
                                 "source": GRIPPER_GEOMETRY_SOURCE, "complete": True,
                                 "component_count": 1, "geoms": ["pad", "palm"]}}


def test_destination_burner_contact_rejects_v2_without_changing_legacy_truth():
    # s13's end flag combined a lifted lower extent, finger contact and burner
    # support. The historical rule did not consider this new support surface.
    samples = [sample_v2(0, supports=("burner",)), sample_v2(.5, supports=("burner",))]
    legacy = sustained_grasp(samples, REFERENCE)
    updated = sustained_grasp_v2(samples, REFERENCE)
    assert legacy["success"] is True
    assert "support_rule" not in legacy
    assert updated["success"] is False
    assert updated["status"] == "failed"
    assert updated["support_rule"] == SUPPORT_RULE_V2
    assert all(check["touching_non_gripper_support"] for check in updated["checks"])


@pytest.mark.parametrize("composite", [False, True])
def test_palm_is_gripper_geometry_and_not_environment_support(monkeypatch, composite):
    import robots.libero.v5_grasp_truth as truth
    component = SimpleNamespace(contact_geoms=["pad", "hand_collision"],
                                important_geoms={"left_fingerpad": ["pad"], "palm": ["palm"]})
    gripper = {"right": component} if composite else component
    names = ["target", "pad", "palm", "hand_collision", "burner"]
    data = SimpleNamespace(time=0., ncon=3, contact=[
        SimpleNamespace(geom1=0, geom2=index, dist=-.001) for index in (1, 2, 3)])
    env = SimpleNamespace(objects_dict={"obj": SimpleNamespace(contact_geoms=["target"])},
        sim=SimpleNamespace(model=SimpleNamespace(geom_id2name=lambda index: names[index]), data=data),
        robots=[SimpleNamespace(gripper=gripper)], _check_grasp=lambda *args: False)
    monkeypatch.setattr(truth, "object_lower_extent", lambda *args: .85)
    first = contact_sample(env, "obj")
    data.time = .5
    second = contact_sample(env, "obj")
    assert first["other_contact_geoms"] == ["hand_collision", "palm"]
    assert first["all_non_gripper_contact_geoms"] == []
    assert first["gripper_geometry"]["geoms"] == ["hand_collision", "pad", "palm"]
    assert first["gripper_geometry"]["source"] == GRIPPER_GEOMETRY_SOURCE
    assert first["gripper_geometry"]["complete"] is True
    assert sustained_grasp_v2([first, second], REFERENCE)["success"] is True
    data.ncon = 4
    data.contact.append(SimpleNamespace(geom1=4, geom2=0, dist=-.001))
    supported = contact_sample(env, "obj")
    assert supported["all_non_gripper_contact_geoms"] == ["burner"]
    assert sustained_grasp_v2([first, supported], REFERENCE)["success"] is False


@pytest.mark.parametrize("missing", ["all_non_gripper_contact_geoms", "gripper_geometry"])
def test_legacy_missing_v2_sample_fields_are_unknown_not_backfilled(missing):
    samples = [sample_v2(0), sample_v2(.5)]
    del samples[-1][missing]
    result = sustained_grasp_v2(samples, REFERENCE)
    assert result["success"] is None
    assert result["status"] == "unknown"
    assert result["unknown_sample_indices"] == [1]
    assert result["checks"][1]["unknown_reason"] == "missing_or_incompatible_v2_contact_fields"
    # Do not derive v2 truth from the old support list, or rewrite legacy truth.
    assert sustained_grasp(samples, REFERENCE)["success"] is True


@pytest.mark.parametrize("field,value", [("complete", False), ("source", "inferred_from_contacts"),
                                        ("version", "unversioned"), ("geoms", [])])
def test_incomplete_or_unversioned_gripper_geometry_is_unknown(field, value):
    samples = [sample_v2(0), sample_v2(.5)]
    samples[0]["gripper_geometry"][field] = value
    assert sustained_grasp_v2(samples, REFERENCE)["success"] is None


def test_contact_sample_marks_missing_complete_component_geometry_unknown(monkeypatch):
    import robots.libero.v5_grasp_truth as truth
    component = SimpleNamespace(important_geoms={"left_fingerpad": ["pad"]})
    data = SimpleNamespace(time=0., ncon=1, contact=[SimpleNamespace(geom1=0, geom2=1, dist=-.001)])
    env = SimpleNamespace(objects_dict={"obj": SimpleNamespace(contact_geoms=["target"])},
        sim=SimpleNamespace(model=SimpleNamespace(geom_id2name=lambda index: ["target", "pad"][index]), data=data),
        robots=[SimpleNamespace(gripper=component)], _check_grasp=lambda *args: False)
    monkeypatch.setattr(truth, "object_lower_extent", lambda *args: .85)
    measured = contact_sample(env, "obj")
    assert measured["finger_contact"] is True
    assert measured["all_non_gripper_contact_geoms"] is None
    assert measured["gripper_geometry"]["complete"] is False
    assert sustained_grasp_v2([measured], REFERENCE)["success"] is None


def test_trace_v2_preserves_first_true_hold_and_rejects_destination_supported_end():
    samples = [sample_v2(.1 * index) for index in range(7)]
    samples += [sample_v2(.7, supports=("burner",))]
    result = grasp_trace_summary_v2(REFERENCE, samples)
    assert result["true_sustained_grasp_during_skill"] is True
    assert result["true_sustained_grasp_at_end"] is False
    assert result["first_sustained_grasp"]["start_sim_time"] == 0
    assert result["first_sustained_grasp"]["end_sim_time"] == .5
    assert result["first_sustained_grasp"]["truth"] == sustained_grasp_v2(samples[:6], REFERENCE)
    assert result["final_hold_window"]["support_rule"] == SUPPORT_RULE_V2
    assert result["samples"] is samples


def test_trace_v2_does_not_bridge_an_unknown_contact_gap_into_true_hold():
    samples = [sample_v2(0), sample(.1), sample_v2(.2), sample_v2(.5)]
    result = grasp_trace_summary_v2(REFERENCE, samples)
    assert result["true_sustained_grasp_during_skill"] is None
    assert result["true_sustained_grasp_at_end"] is None
    assert result["unknown_contact_samples"] == 1
    assert result["final_hold_window"]["status"] == "unknown"


def test_trace_v2_known_long_window_after_unknown_gap_is_still_evidence():
    samples = [sample(0)] + [sample_v2(.1 + .1 * index) for index in range(7)]
    result = grasp_trace_summary_v2(REFERENCE, samples)
    assert result["true_sustained_grasp_during_skill"] is True
    assert result["true_sustained_grasp_at_end"] is True
    assert result["unknown_contact_samples"] == 1
    assert result["first_sustained_grasp"]["truth"]["unknown_sample_indices"] == []


def test_trace_v2_known_support_or_contact_loss_breaks_the_same_window_rule():
    for interrupted in (sample_v2(.3, supports=("burner",)), sample_v2(.3, contact=False)):
        samples = [sample_v2(0), sample_v2(.2), interrupted, sample_v2(.4), sample_v2(.6)]
        result = grasp_trace_summary_v2(REFERENCE, samples)
        assert result["true_sustained_grasp_during_skill"] is False
        assert result["true_sustained_grasp_at_end"] is False
        assert result["first_sustained_grasp"] is None
