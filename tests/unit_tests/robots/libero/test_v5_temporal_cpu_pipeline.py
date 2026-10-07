"""Raw-state isolation and public-only temporal fitting contracts."""

from copy import deepcopy

import numpy as np
import pytest
from PIL import Image

from scripts.prepare_v5_temporal_endpoint_cpu import check_split, encode_sequence
from scripts.train_v5_temporal_endpoint_cpu import metrics
from robots.libero.v5_temporal_verifier import identity


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
