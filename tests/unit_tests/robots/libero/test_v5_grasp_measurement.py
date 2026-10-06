# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
import copy

import numpy as np
import pytest

from robots.libero.v5_grasp_measurement import (
    bind_visible_handle,
    evaluate_grasp_frame,
    evaluate_grasp_pair,
    evaluate_coupled_lift_pair,
)

CALIBRATION = {"closed_empty_max_m": .003, "open_empty_min_m": .078,
               "max_sensor_opening_m": .081, "tolerance_m": .002,
               "minimum_points_per_finger": 5, "provenance": "synthetic_unit_fixture_only"}
FINGERS = {"origin_world": [0, 0, .1], "rotation_world_from_fingers": np.eye(3).tolist(),
           "closing_axis": 0, "depth_half_m": .03, "height_half_m": .03,
           "provenance": "synthetic_unit_fixture_only"}


def measured(step, *, lower_z=0., visible=True, src="perception", centre=(0, 0, .04)):
    return {"id": "e1", "name": "moka pot", "xyz": centre,
            "lower": [-.04, -.02, lower_z], "upper": [.04, .02, lower_z + .08],
            "visible": visible, "source_step": step, "src": src}


def frame(step, **overrides):
    args = {"views": {"agentview": measured(step, lower_z=.08, centre=(0, 0, .12))},
            "opening": .04, "eef_xyz": [0, 0, .1], "previous_step": 0,
            "opening_calibration": CALIBRATION, "finger_frame": FINGERS}
    args.update(overrides)
    return evaluate_grasp_frame(measured(0), **args)


def test_missing_wrist_does_not_overwrite_valid_main_and_inputs_stay_unchanged():
    views = {"agentview": measured(1, lower_z=.08), "wrist": measured(0, visible=False, src="perception_cached")}
    original = copy.deepcopy(views)
    actual = frame(1, views=views)
    assert actual["verified"] is True and actual["selected_view"] == "agentview"
    assert actual["per_view"]["wrist"]["verified"] is None
    assert views == original


@pytest.mark.parametrize("views", [{"agentview": None, "wrist": None},
    {"agentview": measured(1, src="perception_cached")},
    {"agentview": measured(0)}, {"agentview": measured(1, src="sim_truth")}])
def test_missing_cached_stale_or_private_inputs_are_unmeasured(views):
    assert frame(1, views=views)["verified"] is None


def test_opening_missing_calibration_and_wide_missing_geometry_are_unknown():
    assert frame(1, opening_calibration=None)["verified"] is None
    assert frame(1, opening=.0794)["verified"] is None
    assert frame(1, opening=.2)["verified"] is None
    assert frame(1, opening=.001)["verified"] is False


def contact_points(step, opening, *, both=True):
    points = [[side * opening / 2, y, .1] for side in (-1, 1) if both or side == -1
              for y in np.linspace(-.015, .015, 7)]
    return {"agentview": {"xyz_world": points, "src": "perception", "source_step": step, "object_id": "e1"}}


def test_wide_opening_needs_current_measured_points_at_both_fingers():
    actual = frame(1, opening=.0794, measured_points_by_view=contact_points(1, .0794))
    assert actual["verified"] is True
    opening = actual["per_view"]["agentview"]["opening_evidence"]
    assert opening["points_per_finger"] == [7, 7]
    assert frame(1, opening=.0794, measured_points_by_view=contact_points(1, .0794, both=False))["verified"] is False
    assert frame(1, opening=.0794, measured_points_by_view=contact_points(0, .0794))["verified"] is None
    uncalibrated = {**CALIBRATION, "minimum_points_per_finger": None}
    assert frame(1, opening=.0794, opening_calibration=uncalibrated,
                 measured_points_by_view=contact_points(1, .0794))["verified"] is None


def test_proprioceptive_finger_rotation_is_used():
    fingers = {**FINGERS, "rotation_world_from_fingers": [[0, -1, 0], [1, 0, 0], [0, 0, 1]]}
    points = contact_points(1, .0794)
    points["agentview"]["xyz_world"] = [[-y, x, z] for x, y, z in points["agentview"]["xyz_world"]]
    assert frame(1, opening=.0794, finger_frame=fingers, measured_points_by_view=points)["verified"] is True


def test_bad_robot_rotation_is_rejected():
    with pytest.raises(ValueError, match="proper proprioceptive rotation"):
        frame(1, finger_frame={**FINGERS, "rotation_world_from_fingers": np.zeros((3, 3)).tolist()})


def test_pan_needs_measured_original_support_clearance_not_only_centre_rise():
    assert frame(1, require_support_clearance=True)["verified"] is None
    assert frame(1, require_support_clearance=True, support_top_z_m=.07)["verified"] is False
    assert frame(1, require_support_clearance=True, support_top_z_m=.04)["verified"] is True


@pytest.mark.parametrize("require_support,lower_z,support_top", [
    (False, .01, None), (True, .08, .07),
])
def test_numpy_measurement_false_conditions_cannot_verify_grasp(require_support, lower_z, support_top):
    measured_entity = measured(1, lower_z=np.float64(lower_z))
    actual = frame(1, views={"agentview": measured_entity},
                   require_support_clearance=require_support, support_top_z_m=support_top)
    assert actual["verified"] is False
    assert all(value is None or type(value) is bool for value in actual["per_view"]["agentview"]["conditions"].values())


def test_disagreement_between_two_current_views_stays_unknown():
    actual = frame(1, views={"agentview": measured(1, lower_z=.08), "wrist": measured(1, lower_z=.01)})
    assert actual["verified"] is None and actual["reason"] == "fresh_views_disagree"


def test_pair_requires_two_current_captures_and_registered_interval():
    assert evaluate_grasp_pair(frame(1), frame(2), .3)["verified"] is True
    assert evaluate_grasp_pair(frame(1), frame(1), .3)["verified"] is False
    assert evaluate_grasp_pair(frame(1), frame(2), .1)["verified"] is False
    unknown = frame(2, views={"agentview": None})
    assert evaluate_grasp_pair(frame(1), unknown, .3)["verification"] == "unmeasured"
    repeated = frame(np.int64(1))
    assert evaluate_grasp_pair(repeated, repeated, np.float64(.3))["verified"] is False


def test_object_away_from_measured_fingers_is_not_verified():
    assert frame(1, eef_xyz=[.8, 0, .1], finger_frame=None)["verified"] is False


def test_other_object_detection_or_points_do_not_verify_selected_object():
    assert frame(1, views={"agentview": {**measured(1, lower_z=.08), "id": "e2"}})["verified"] is None
    points = contact_points(1, .0794)
    points["agentview"]["object_id"] = "e2"
    assert frame(1, opening=.0794, measured_points_by_view=points)["verified"] is None


def test_bound_visible_handle_can_supply_occluded_finger_geometry():
    body = measured(1, lower_z=.08)
    body.update(lower=[-.12, -.02, .08], upper=[-.05, .02, .16], xyz=[-.085, 0, .12])
    cloud = [[x, y, .1] for x in np.linspace(-.01, .01, 4) for y in (-.005, .005, 0)]
    handle, reason = bind_visible_handle(measured(0), body, cloud)
    assert reason == "bound_current_visible_handle"
    actual = frame(1, views={"agentview": body}, handle_measurements_by_view={"agentview": handle})
    assert actual["verified"] is True
    assert actual["per_view"]["agentview"]["finger_geometry"]["handle_measurement"]["object_id"] == "e1"


def test_missing_stale_or_other_object_handle_stays_unmeasured():
    body = measured(1, lower_z=.08)
    body.update(lower=[-.12, -.02, .08], upper=[-.05, .02, .16], xyz=[-.085, 0, .12])
    handle, _ = bind_visible_handle(measured(0), body, [[0, 0, .1]] * 10)
    for candidate in (None, {**handle, "source_step": 0}, {**handle, "object_id": "e2"}):
        assert frame(1, views={"agentview": body},
                     handle_measurements_by_view={"agentview": candidate})["verified"] is None
    rejected, reason = bind_visible_handle(measured(0), body, [[.8, 0, .1]] * 10)
    assert rejected is None and reason == "handle_outside_selected_measured_object_envelope"


def test_current_wrist_handle_can_verify_body_seen_only_in_main_view():
    body = measured(1, lower_z=.08)
    body.update(lower=[-.12, -.02, .08], upper=[-.05, .02, .16], xyz=[-.085, 0, .12])
    handle, _ = bind_visible_handle(measured(0), body, [[0, 0, .1]] * 10)
    handle["camera"] = "wrist"
    args = dict(views={"agentview": body}, handle_measurements_by_view={"wrist": handle})
    assert frame(1, **args)["verified"] is None
    actual = frame(1, **args, cross_view_handle_v1=True)
    assert actual["verified"] is True and actual["selected_view"] == "agentview"
    evidence = actual["per_view"]["agentview"]["finger_geometry"]
    assert evidence["current_handle_views"][0]["camera"] == "wrist"
    assert "wrist" not in actual["per_view"]
    for override in ({"source_step": 0}, {"object_id": "e2"}, {"src": "sim_truth"}, {"camera": "agentview"}):
        assert frame(1, views={"agentview": body}, cross_view_handle_v1=True,
                     handle_measurements_by_view={"wrist": {**handle, **override}})["verified"] is None


def test_cross_view_handle_does_not_override_support_or_empty_gripper():
    body = measured(1, lower_z=.08)
    body.update(lower=[-.12, -.02, .08], upper=[-.05, .02, .16], xyz=[-.085, 0, .12])
    handle, _ = bind_visible_handle(measured(0), body, [[0, 0, .1]] * 10)
    args = dict(views={"agentview": body}, cross_view_handle_v1=True,
                handle_measurements_by_view={"wrist": handle})
    assert frame(1, **args, opening=.001)["verified"] is False
    assert frame(1, **args, require_support_clearance=True, support_top_z_m=.07)["verified"] is False


def occluded_coupled_frames():
    frames = []
    for step, height in ((1, .08), (2, .13)):
        body = measured(step, lower_z=height, centre=(-.085, 0, height + .04))
        body.update(lower=[-.12, -.02, height], upper=[-.05, .02, height + .08])
        fingers = {**FINGERS, "origin_world": [0, 0, height + .02]}
        actual = frame(step, views={"agentview": body}, eef_xyz=[0, 0, height + .02],
                       finger_frame=fingers, handle_measurements_by_view={},
                       cross_view_handle_v1=True, require_support_clearance=True, support_top_z_m=0.)
        actual["body_quat_xyzw"] = [0, 0, 0, 1]
        frames.append(actual)
    return frames


def test_active_body_motion_can_measure_occluded_handle_without_mutating_source():
    first, second = occluded_coupled_frames()
    saved = copy.deepcopy([first, second])
    assert first["verified"] is None and second["verified"] is None
    actual = evaluate_coupled_lift_pair(first, second, .5)
    assert actual["verified"] is True
    assert actual["coupled_lift_evidence"]["per_view"]["agentview"]["coupling_measured"] is True
    assert [first, second] == saved


@pytest.mark.parametrize("fault", ["stationary_body", "no_robot_motion", "rotation", "cached", "other_object", "same_capture"])
def test_active_motion_requires_the_same_current_body_to_follow_translation(fault):
    first, second = occluded_coupled_frames()
    body = second["per_view"]["agentview"]["measurement"]
    if fault == "stationary_body":
        body["xyz"] = first["per_view"]["agentview"]["measurement"]["xyz"]
    elif fault == "no_robot_motion":
        second["eef_xyz"] = first["eef_xyz"]
    elif fault == "rotation":
        second["body_quat_xyzw"] = [0, 0, .70710678, .70710678]
    elif fault == "cached":
        body["src"] = "perception_cached"
    elif fault == "other_object":
        body["id"] = "e2"
    else:
        body["source_step"] = first["per_view"]["agentview"]["measurement"]["source_step"]
    assert evaluate_coupled_lift_pair(first, second, .5)["verified"] is None


@pytest.mark.parametrize("condition", ["measured_lower_lift", "calibrated_nonempty_opening", "original_measured_support_clearance"])
def test_active_motion_never_overrides_a_measured_rejection(condition):
    first, second = occluded_coupled_frames()
    view = second["per_view"]["agentview"]
    view["conditions"][condition] = False
    view["verified"] = False
    second.update(verified=False, selected_view="agentview")
    assert evaluate_coupled_lift_pair(first, second, .5)["verified"] is False
