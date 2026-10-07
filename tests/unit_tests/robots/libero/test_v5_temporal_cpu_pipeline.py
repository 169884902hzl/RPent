"""Raw-state isolation and public-only temporal fitting contracts."""

from copy import deepcopy

import numpy as np
import pytest
from PIL import Image

from scripts.prepare_v5_temporal_endpoint_cpu import check_split, encode_sequence
from scripts.train_v5_temporal_endpoint_cpu import metrics
from robots.libero.v5_temporal_verifier import (
    feature_encoder_identity, identity, infer, model_features, model_transform_identity,
)


def test_raw_state_split_rejects_repeated_state_and_confirmation_derivation():
    cases = [{"raw_state_sha256": "same", "split": "train"},
             {"raw_state_sha256": "same", "split": "validation"}]
    with pytest.raises(ValueError, match="both train and validation"):
        check_split(cases, set())
    with pytest.raises(ValueError, match="confirmation"):
        check_split([cases[0]], {"same"})


def test_private_endpoint_does_not_change_public_features(tmp_path):
    image = tmp_path / "rgb.png"
    world = tmp_path / "world.npz"
    Image.fromarray(np.zeros((16, 16, 3), dtype=np.uint8)).save(image)
    np.savez_compressed(world, array=np.full((16, 16, 3), .5))
    frame = {"source_step": 0, "views": {"agentview": {"raw_rgb": identity(image), "raw_world": identity(world)}},
             "public_robot_observation": {"eef_xyz_m": [0, 0, 1], "gripper_opening_m": .08}}
    frames = [deepcopy(frame) for _ in range(3)]
    bounds = {"lower": [0, 0, 0], "upper": [1, 1, 1]}
    first = encode_sequence(frame, frames, bounds)[0]
    frame["private_joint_qpos"] = [999]
    for recent in frames:
        recent["private_endpoint_satisfied"] = True
    second = encode_sequence(frame, frames, bounds)[0]
    np.testing.assert_array_equal(first, second)


def test_measurement_absence_is_unknown_even_if_a_private_label_exists():
    frame = {"source_step": 0, "views": {},
             "public_robot_observation": {"eef_xyz_m": [0, 0, 1], "gripper_opening_m": .08}}
    _, available, reason = encode_sequence(frame, [frame] * 3, {"lower": [0, 0, 0], "upper": [1, 1, 1]})
    assert available == [False, False]
    assert reason == "fixture_unmeasured_in_both_views"


def test_endpoint_metrics_count_both_false_stop_directions():
    result = metrics(np.array([1, 1, 0, 0]), np.array([.9, .1, .8, .2]))
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 1)
    assert result["precision"] == result["recall"] == .5


def test_baseline_relative_features_ignore_a_shared_scene_appearance_shift():
    rng = np.random.default_rng(10)
    vector = rng.normal(size=(2, 2578)).astype(np.float32)
    shifted = vector.copy()
    shift = rng.normal(size=(2, 640)).astype(np.float32)
    for frame in range(4):
        shifted[:, frame * 640:(frame + 1) * 640] += shift
    relative = model_features(vector, "baseline_relative_v1")
    np.testing.assert_allclose(relative, model_features(shifted, "baseline_relative_v1"), atol=1e-6)
    np.testing.assert_array_equal(relative[:, 2560:], vector[:, 2560:])


def test_runtime_relative_transform_matches_cpu_and_rejects_changed_transform(tmp_path):
    vector = np.arange(2578, dtype=np.float32) / 2578
    weights = np.zeros(2578, dtype=np.float32)
    weights[641] = 1
    checkpoint = tmp_path / "relative.npz"
    values = dict(mean=np.zeros(2578, dtype=np.float32), scale=np.ones(2578, dtype=np.float32),
                  output_weight=weights, output_bias=np.asarray(0.), supports_modes=np.asarray(["turn_off"]),
                  feature_encoder_sha256=np.asarray(feature_encoder_identity()),
                  feature_transform=np.asarray("baseline_relative_v1"),
                  feature_transform_sha256=np.asarray(model_transform_identity()))
    np.savez(checkpoint, **values)
    result = infer(vector, [True, True], checkpoint, requested_mode="turn_off")
    expected = 1 / (1 + np.exp(-model_features(vector, "baseline_relative_v1")[641]))
    assert result["p_satisfied"] == pytest.approx(expected)
    assert result["stop_admitted"] is False
    values["feature_transform_sha256"] = np.asarray("changed")
    np.savez(checkpoint, **values)
    assert infer(vector, [True, True], checkpoint, requested_mode="turn_off")["reason"] == "temporal_model_feature_transform_mismatch"
