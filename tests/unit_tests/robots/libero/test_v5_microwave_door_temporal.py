"""Public multi-frame geometry rejects missing and contradictory evidence."""

import copy
import math

import numpy as np
import pytest

from robots.libero.v5_microwave_door_temporal import measure_microwave_door_temporal


def plane(angle, centre, identity):
    radians = math.radians(angle)
    return {"centre": centre, "normal_xy": [math.cos(radians), math.sin(radians)],
            "residual_p90_m": .002, "points": 200, "mask_count": 1,
            "mask_id": identity, "source_cameras": ["agentview", "wrist"]}


def observation(step, time, angle, *, door_centre=None):
    return {"source": "perception", "frame_id": "world", "length_unit": "m",
            "source_step": step, "timestamp_s": time, "arm_withdrawn": True,
            "occluded": False, "frame_moving_mask_overlap": .01,
            "frame": plane(0, [0., 0., 1.], f"frame-{step}"),
            "moving": plane(angle, door_centre or [.01, .1, 1.], f"door-{step}")}


def capture_pair(before_angle=0., after_angle=60.):
    return ([observation(1, 0., before_angle), observation(2, .3, before_angle)],
            [observation(10, 1., after_angle), observation(11, 1.3, after_angle)])


def test_public_open_endpoint_and_default_disabled_stop():
    before, after = capture_pair()
    measured = measure_microwave_door_temporal(before, after, "open")
    assert measured["status"] == "measured" and measured["endpoint_reached"] is True
    assert measured["angle_change_deg"] == pytest.approx(60)
    assert measured["requested_direction_observed"] is True
    assert measured["stop_admitted"] is False
    assert measured["observations"][-1]["moving"]["source_cameras"] == ["agentview", "wrist"]


def test_development_stop_requires_enabled_and_stable_public_endpoint():
    before, after = capture_pair(60., 0.)
    assert not measure_microwave_door_temporal(before, after, "close")["stop_admitted"]
    measured = measure_microwave_door_temporal(before, after, "close", endpoint_stop_enabled=True)
    assert measured["endpoint_reached"] is True and measured["stop_admitted"] is True
    assert measured["angle_change_deg"] == pytest.approx(-60)


def test_stable_incomplete_motion_is_measured_false_and_not_admitted():
    before, after = capture_pair(0., 20.)
    measured = measure_microwave_door_temporal(before, after, "open", endpoint_stop_enabled=True)
    assert measured["status"] == "measured" and measured["endpoint_reached"] is False
    assert measured["stop_admitted"] is False


def test_already_at_endpoint_can_stop_but_does_not_claim_requested_motion():
    before, after = capture_pair(0., 0.)
    measured = measure_microwave_door_temporal(before, after, "close", endpoint_stop_enabled=True)
    assert measured["stop_admitted"] is True
    assert measured["requested_direction_observed"] is False


def test_plane_eigenvector_sign_does_not_create_a_door_motion():
    before, after = capture_pair(60., 0.)
    for key in ("frame", "moving"):
        after[-1][key]["normal_xy"] = [-x for x in after[-1][key]["normal_xy"]]
    assert measure_microwave_door_temporal(before, after, "close")["endpoint_reached"] is True


@pytest.mark.parametrize("corruption, reason", [
    (lambda sample: sample.pop("frame"), "frame_plane_not_measured"),
    (lambda sample: sample["moving"].update(mask_count=2), "moving_mask_missing_or_ambiguous"),
    (lambda sample: sample["moving"].update(mask_count=True), "moving_mask_missing_or_ambiguous"),
    (lambda sample: sample.update(frame_moving_mask_overlap=.8), "frame_and_door_masks_overlap_or_invalid"),
    (lambda sample: sample.update(occluded=True), "unobstructed_after_withdrawal_not_measured"),
    (lambda sample: sample.update(arm_withdrawn=False), "unobstructed_after_withdrawal_not_measured"),
    (lambda sample: sample.update(frame_id="camera"), "public_world_metres_provenance_missing"),
    (lambda sample: sample.update(timestamp_s=float("nan")), "timestamp_missing_or_invalid"),
    (lambda sample: sample["moving"].update(source_step=1), "moving_plane_source_step_not_current"),
    (lambda sample: sample["moving"].update(normal_xy=[0., 0.]), "moving_plane_measurement_not_supported"),
    (lambda sample: sample["moving"].update(source="sim_truth"), "moving_public_world_metres_provenance_missing"),
    (lambda sample: sample["moving"].update(mask_id=sample["frame"]["mask_id"]), "frame_and_door_share_same_measurement"),
])
def test_unknown_evidence_never_stops(corruption, reason):
    before, after = capture_pair()
    corruption(after[-1])
    measured = measure_microwave_door_temporal(before, after, "open", endpoint_stop_enabled=True)
    assert measured["status"] == "unmeasured" and measured["endpoint_reached"] is None
    assert measured["reason"] == reason and measured["stop_admitted"] is False


def test_retreat_mask_ambiguity_without_valid_counts_is_unknown():
    before, after = capture_pair()
    after[0]["measurement_counts"] = None
    after[0]["moving"].pop("mask_count")
    assert measure_microwave_door_temporal(before, after, "open")["status"] == "unmeasured"


def test_repeated_or_tightly_spaced_frames_cannot_establish_stability():
    before, after = capture_pair()
    assert measure_microwave_door_temporal(before, after[:1], "open")["endpoint_reached"] is None
    after[1]["timestamp_s"] = 1.1
    assert measure_microwave_door_temporal(before, after, "open")["reason"] == "after_captures_not_distinct_and_time_separated"
    after[1] = copy.deepcopy(after[0])
    assert measure_microwave_door_temporal(before, after, "open")["status"] == "unmeasured"


@pytest.mark.parametrize("change", ["frame_drift", "frame_angle", "door_angle", "door_translation"])
def test_reference_drift_or_endpoint_reversal_is_unknown(change):
    before, after = capture_pair()
    if change == "frame_drift":
        after[-1]["frame"]["centre"][0] += .05
    elif change == "frame_angle":
        after[-1]["frame"]["normal_xy"] = [math.cos(.5), math.sin(.5)]
    elif change == "door_angle":
        after[-1]["moving"]["normal_xy"] = [1., 0.]
    else:
        after[-1]["moving"]["centre"][1] += .05
    measured = measure_microwave_door_temporal(before, after, "open")
    assert measured["status"] == "unmeasured" and measured["endpoint_reached"] is None


def test_raw_world_clouds_reuse_existing_vertical_plane_fitter():
    before, after = capture_pair(0., 60.)
    for sample in before + after:
        for kind in ("frame", "moving"):
            record = sample[kind]
            normal = np.asarray(record["normal_xy"])
            tangent = np.array([-normal[1], normal[0]])
            centre = np.asarray(record["centre"])
            record["points_world"] = np.array([centre + np.array([*(tangent * y), z])
                                               for y in np.linspace(-.1, .1, 20)
                                               for z in np.linspace(-.1, .1, 10)])
            for key in ("normal_xy", "centre", "residual_p90_m", "points"):
                record.pop(key)
    measured = measure_microwave_door_temporal(before, after, "open")
    assert measured["endpoint_reached"] is True
    assert measured["observations"][-1]["moving"]["points"] == 200


def test_simulator_labels_do_not_influence_public_measurement():
    before, after = capture_pair(0., 20.)
    baseline = measure_microwave_door_temporal(before, after, "open")
    for sample in before + after:
        sample["sim_truth"] = {"door_joint": 1.57, "solved": True}
        sample["private_endpoint"] = True
    assert measure_microwave_door_temporal(before, after, "open") == baseline
