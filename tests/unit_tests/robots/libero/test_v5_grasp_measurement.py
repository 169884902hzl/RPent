import copy

import numpy as np
import pytest

from robots.libero.v5_grasp_measurement import evaluate_grasp_frame, evaluate_grasp_pair


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
    args = dict(views={"agentview": measured(step, lower_z=.08, centre=(0, 0, .12))},
                opening=.04, eef_xyz=[0, 0, .1], previous_step=0,
                opening_calibration=CALIBRATION, finger_frame=FINGERS)
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
