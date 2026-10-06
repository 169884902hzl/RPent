"""Public stove color evidence cannot mistake occlusion for switched-off coils."""

from dataclasses import replace
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from robots.libero.v5_state import Entity
from robots.libero.v5_stove_measurement import (
    DEFAULT_PARAMETERS, VERSION, measure_stove_rgbd, measured_stove_endpoint, measure_stove_control_features,
)


def scene(red=False, *, size=64):
    yy, xx = np.mgrid[-.08:.08:complex(size), -.08:.08:complex(size)]
    world = np.stack((xx, yy, np.full_like(xx, .10)), axis=-1)
    image = np.full((size, size, 3), 30, dtype=np.uint8)
    ring = np.abs(np.sqrt(xx**2+yy**2)-.035) < .007
    if red:
        image[ring] = (220, 15, 15)
    obj = Entity("e2", "stove", (0.,0.,.09), (-.08,-.08,.08), (.08,.08,.10))
    return image, world, obj


def measurement(red, step, *, camera="agentview", size=64):
    image, world, obj = scene(red, size=size)
    return measure_stove_rgbd(image, world, obj, step, camera)


def test_visible_red_coils_establish_on_and_request_off_has_explicit_negative_evidence():
    before, after = measurement(False, 0), measurement(True, 1)
    assert before["state"] == "unmeasured"
    assert after["state"] == "on"
    assert measured_stove_endpoint(before, after, "turn_on")[0] is True
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is False and evidence["state"] == "on"


def test_visible_dark_coils_do_not_establish_the_control_off_endpoint():
    before, after = measurement(True, 0), measurement(False, 1)
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is None and evidence["state"] == "unmeasured"
    assert evidence["observed_coil_state"] == "dark"
    assert evidence["reason"] == "dark_coils_do_not_measure_control_off_endpoint"
    assert evidence["reference_support"]["coverage"] == 1
    assert evidence["reference_support"]["red_fraction"] == 0
    assert measured_stove_endpoint(before, after, "turn_on")[0] is None


def test_exact_original_job3643_dark_intermediate_control_is_not_verified_off():
    root = Path(__file__).resolve().parents[4]
    path = root / "results/harness_v5/stove518_endpoint_FP_original_CPU_20261005/preparation/selected_evidence.json"
    record = json.loads(path.read_text())
    evidence = record["first_attempt"]["verification_measurements"]["stove_rgbd"]
    # The private fields are diagnostic labels only. Verification consumes
    # precisely the original public RGB-D evidence, without private qpos.
    assert record["first_attempt"]["private_after"]["satisfied"] is False
    assert evidence["before"]["features"]["red_pixels"] == 1865
    assert evidence["after"]["features"]["red_pixels"] == 0
    verified, public = measured_stove_endpoint(evidence["before"], evidence["after"], "turn_off")
    assert verified is None
    assert public["reference_support"]["matched"] == 28
    assert public["reference_support"]["changed_or_occluded"] == 0
    assert public["reason"] == "dark_coils_do_not_measure_control_off_endpoint"


def test_dark_first_observation_cannot_prove_off_without_known_on_reference():
    verified, evidence = measured_stove_endpoint(measurement(False, 0), measurement(False, 1), "turn_off")
    assert verified is None and evidence["state"] == "unmeasured"
    assert evidence["reason"] == "off_requires_known_on_reference"


def test_absent_wrist_red_is_not_off_even_when_its_known_on_support_is_dark():
    before, after = measurement(True, 0, camera="wrist"), measurement(False, 1, camera="wrist")
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is None and evidence["reason"] == "off_requires_main_view"
    assert measured_stove_endpoint(before, measurement(True, 1, camera="wrist"), "turn_on")[0] is True


@pytest.mark.parametrize("height", [.003, .03, .15])
def test_object_or_gripper_depth_over_the_known_coils_cannot_establish_off(height):
    before = measurement(True, 0)
    image, world, obj = scene(False)
    for r, c, *_ in before["red_support_anchors"]:
        world[r,c,2] += height
    after = measure_stove_rgbd(image, world, obj, 1, "agentview")
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is None and evidence["state"] == "unmeasured"
    assert evidence["reference_support"]["changed_or_occluded"] == len(before["red_support_anchors"])


def test_missing_depth_or_coils_out_of_view_is_unmeasured():
    before = measurement(True, 0)
    image, world, obj = scene(False)
    for r, c, *_ in before["red_support_anchors"]:
        world[r,c] = np.nan
    after = measure_stove_rgbd(image, world, obj, 1, "agentview")
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is None and evidence["reference_support"]["coverage"] == 0


def test_remaining_red_reference_pixels_prevent_off_when_global_fraction_is_small():
    before = measurement(True, 0)
    image, world, obj = scene(False)
    for r, c, *_ in before["red_support_anchors"][:10]:
        image[r,c] = (220, 15, 15)
    after = measure_stove_rgbd(image, world, obj, 1, "agentview")
    assert after["state"] == "unmeasured"
    verified, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert verified is None and evidence["reason"] == "known_on_red_support_not_clearly_off"


def test_red_object_above_the_stove_support_plane_does_not_prove_stove_on():
    image, world, obj = scene(True)
    red = image[...,0] > 100
    world[red,2] += .025
    after = measure_stove_rgbd(image, world, obj, 1, "agentview")
    assert after["features"]["red_pixels"] == 0 and after["state"] == "unmeasured"
    assert measured_stove_endpoint(measurement(False,0),after,"turn_on")[0] is None


@pytest.mark.parametrize("change", ["camera", "resolution", "step", "visibility", "entity", "older_step"])
def test_stale_or_incomparable_off_reference_is_unmeasured(change):
    before = measurement(True, 2 if change == "older_step" else 0)
    after = measurement(False, 0 if change == "step" else 1,
                        camera="main" if change == "camera" else "agentview",
                        size=128 if change == "resolution" else 64)
    if change == "visibility":
        image, world, obj = scene(False)
        after = measure_stove_rgbd(image, world, replace(obj, visible=False), 1, "agentview")
    if change == "entity":
        after["entity"] = "e3"
    assert measured_stove_endpoint(before, after, "turn_off")[0] is None


def test_measurements_are_json_safe_perception_evidence_and_receipt_evidence_is_compact():
    before, after = measurement(True,0), measurement(False,1)
    assert before["version"] == VERSION and before["src"] == "perception"
    assert len(before["red_support_anchors"]) <= DEFAULT_PARAMETERS.maximum_red_anchors
    assert len(before["support_samples"]) <= DEFAULT_PARAMETERS.sample_grid_resolution**2
    json.dumps(before, allow_nan=False)
    _, evidence = measured_stove_endpoint(before, after, "turn_off")
    assert "support_samples" not in evidence["before"]
    assert "red_support_anchors" not in evidence["after"]
    json.dumps(evidence, allow_nan=False)


def test_bad_rgb_depth_contracts_are_rejected_and_invalid_depth_is_not_evidence():
    image, world, obj = scene(True)
    with pytest.raises(ValueError, match="matching"):
        measure_stove_rgbd(image[:-1],world,obj,0,"agentview")
    with pytest.raises(ValueError, match="intensity scale"):
        measure_stove_rgbd(image.astype(float)/255,world,obj,0,"agentview")
    assert measure_stove_rgbd(image,np.zeros_like(world),obj,0,"agentview")["state"] == "unmeasured"
    with pytest.raises(ValueError, match="turn_on/turn_off"):
        measured_stove_endpoint(None,None,"open")


def test_two_fully_visible_stable_dark_frames_do_not_verify_the_control_off_endpoint():
    before, first, second = measurement(True, 0), measurement(False, 1), measurement(False, 2)
    verified, evidence = measured_stove_endpoint(before, first, "turn_off",
                                                second_after=second, interval_s=.3)
    assert verified is None and evidence["state"] == "unmeasured"
    assert evidence["observed_coil_state"] == "dark"
    assert evidence["visual_transition"] == "known_on_surface_fully_visible_and_stably_dark_in_two_frames"
    assert evidence["reason"] == "stable_dark_coils_do_not_measure_control_off_endpoint"
    assert evidence["complete_region_visibility"] == {
        "reference_pixels": 4096, "first_coverage": 1., "second_coverage": 1.}
    assert evidence["second_reference_support"]["coverage"] == 1
    assert evidence["measurement_scope"] == "visible_stove_on_to_dark_transition_not_joint_endpoint"
    assert "surface_region" not in evidence["second_after"]


def test_three_recorded_job4128_dark_false_positives_remain_unmeasured_without_control_evidence():
    root = Path(__file__).resolve().parents[4]
    path = root / "results/harness_v5/stove551_off_endpoint_CPU_20261006/recorded_public_cases.json.gz"
    cases = json.loads(gzip.decompress(path.read_bytes()))
    assert len(cases) == 3
    for case in cases:
        # Preserve the old verdict and diagnostic label. Only the original
        # public RGB-D packet is passed to the repaired endpoint verifier.
        assert case["original_public_verdict"] is True
        assert case["original_private_label"] is False
        packet = case["public_packet"]
        verified, evidence = measured_stove_endpoint(packet["before"], packet["after"], "turn_off",
            second_after=packet["second_after"], interval_s=packet["measurement_interval_s"])
        assert verified is None, case["case"]
        assert evidence["state"] == "unmeasured"
        assert evidence["observed_coil_state"] == "dark"
        assert evidence["visual_transition"] == "known_on_surface_fully_visible_and_stably_dark_in_two_frames"
        assert evidence["reason"] == "stable_dark_coils_do_not_measure_control_off_endpoint"


@pytest.mark.parametrize("change,reason", [
    ("interval", "off_requires_separated_stable_frames"),
    ("stale", "off_second_frame_not_new_or_visible"),
    ("different_entity", "off_second_frame_geometry_changed"),
    ("missing_region", "complete_surface_region_not_recorded"),
])
def test_off_transition_requires_new_stable_frames_and_recorded_full_region(change, reason):
    before, first, second = measurement(True, 0), measurement(False, 1), measurement(False, 2)
    interval = .29 if change == "interval" else .3
    if change == "stale":
        second["source_step"] = 1
    elif change == "different_entity":
        second["entity"] = "e7"
    elif change == "missing_region":
        before.pop("surface_region")
    verified, evidence = measured_stove_endpoint(before, first, "turn_off",
                                                second_after=second, interval_s=interval)
    assert verified is None and evidence["reason"] == reason


@pytest.mark.parametrize("phase", ["first", "second"])
def test_nonred_part_of_known_stove_occluded_in_either_frame_cannot_verify_off(phase):
    before = measurement(True, 0)
    first, second = measurement(False, 1), measurement(False, 2)
    image, world, obj = scene(False)
    world[0, 0] = np.nan  # not a sampled red anchor; full-region audit still sees it
    changed = measure_stove_rgbd(image, world, obj, 1 if phase == "first" else 2, "agentview")
    if phase == "first":
        first = changed
    else:
        second = changed
    verified, evidence = measured_stove_endpoint(before, first, "turn_off",
                                                second_after=second, interval_s=.3)
    assert verified is None and evidence["reason"] == "known_on_surface_region_occluded_or_unmeasured"
    assert evidence["reference_support"]["coverage"] == 1


def test_red_reappearing_in_second_frame_is_explicit_off_failure():
    verified, evidence = measured_stove_endpoint(measurement(True, 0), measurement(False, 1), "turn_off",
        second_after=measurement(True, 2), interval_s=.3)
    assert verified is False and evidence["state"] == "on"


def test_changing_low_red_fraction_does_not_count_as_stable_off():
    image, world, obj = scene(False)
    image[:5, :6] = (220, 15, 15)
    second = measure_stove_rgbd(image, world, obj, 2, "agentview")
    assert second["state"] == "unmeasured"
    verified, evidence = measured_stove_endpoint(measurement(True, 0), measurement(False, 1), "turn_off",
                                                second_after=second, interval_s=.3)
    assert verified is None and evidence["reason"] == "off_red_fraction_not_stable"


@pytest.mark.parametrize("native_done", [False, True])
def test_runtime_off_verification_captures_actual_second_frame_without_truth_reads(monkeypatch, native_done):
    from types import SimpleNamespace
    from robots.libero.v5_runtime import V5Executor
    from robots.libero import v5_runtime

    before, first, second = measurement(True, 0), measurement(False, 1), measurement(False, 2)
    readings, captures, controls = iter([first, second]), [], []
    executor = V5Executor.__new__(V5Executor)
    executor.measure_stove = lambda parent: next(readings)
    executor.capture = lambda: captures.append(True)
    executor.last_verification_measurements, executor.motion_evidence = {}, []
    executor.p = SimpleNamespace(env=SimpleNamespace(terminated=native_done, truncated=False),
        set_gripper=lambda **options: controls.append(options) or {"steps_used": 20})
    ticks = iter([10., 10.4, 10.42])
    monkeypatch.setattr(v5_runtime.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(v5_runtime.time, "sleep", lambda duration: pytest.fail("clock already advanced"))
    verified, evidence = executor.verify_stove(scene()[2], before, "turn_off")
    assert verified is None and evidence["state"] == "unmeasured" and captures == [True]
    assert controls == ([] if native_done else [{"gripper": 0., "steps": 20}])
    packet = executor.last_verification_measurements["stove_rgbd"]
    assert packet["after"]["source_step"] == 1 and packet["second_after"]["source_step"] == 2
    assert packet["measurement_interval_s"] == pytest.approx(.42)
    assert evidence["measurement_scope"] == "visible_stove_on_to_dark_transition_not_joint_endpoint"


def control_scene():
    parent = Entity("e2", "stove", (0., 0., 1.), (-.1, -.1, .98), (.1, .1, 1.01), source_step=6)
    cloud = np.array([(x, y, 1.03) for x in np.linspace(.05, .09, 20) for y in np.linspace(.04, .07, 10)])
    return parent, cloud


def test_current_control_pca_does_not_fabricate_a_directed_lever_or_endpoint():
    parent, cloud = control_scene()
    result = measure_stove_control_features(cloud, parent, (.3, .3, 1.5), source_step=6, camera="wrist")
    assert result["control_pose"] is not None
    assert result["undirected_axis_xy"] is not None
    assert result["directed_lever"] is None and result["stove_reference"] is None
    assert result["signed_angle_to_reference_deg"] is None
    assert result["endpoint_state"] == "unmeasured"


def test_separately_measured_pivot_tip_and_stove_front_record_direction_without_an_endpoint_claim():
    parent, cloud = control_scene()
    offsets = np.array([(x, y, 0.) for x in np.linspace(-.001, .001, 6) for y in np.linspace(-.001, .001, 6)])
    features = {"pivot": offsets + [.058, .055, 1.03], "tip": offsets + [.084, .055, 1.03],
                "shell": offsets + [0., 0., 1.], "front_edge": offsets + [0., .07, 1.]}
    result = measure_stove_control_features(cloud, parent, (.3, .3, 1.5), source_step=6,
        camera="wrist", feature_points=features)
    assert result["directed_lever"]["vector_xy"] == pytest.approx([1., 0.])
    assert result["stove_reference"]["vector_xy"] == pytest.approx([0., 1.])
    assert result["signed_angle_to_reference_deg"] == pytest.approx(-90.)
    assert result["endpoint_state"] == "unmeasured"
    features["tip"] += [.3, 0., 0.]
    rejected = measure_stove_control_features(cloud, parent, (.3, .3, 1.5), source_step=6,
        camera="wrist", feature_points=features)
    assert rejected["directed_lever"] is None and rejected["signed_angle_to_reference_deg"] is None
    assert "tip" in rejected["unmeasured_features"]


def test_stale_parent_cannot_bind_a_current_stove_control():
    parent, cloud = control_scene()
    result = measure_stove_control_features(cloud, parent, (.3, .3, 1.5), source_step=7, camera="wrist")
    assert result["control_pose"] is None
    assert result["reason"] == "current_parent_not_measured_in_same_capture"
