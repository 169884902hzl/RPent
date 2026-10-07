import copy
import hashlib
import json

import pytest

from robots.libero.v5_confirmation_exclusions import (
    check_registered_training_layout,
    check_registered_training_original_state,
    check_training_layout,
)


@pytest.fixture
def registry():
    return {"schema": "libero_confirmation_exclusions/1", "training_allowed": False,
            "minimum_moka_xy_distance_m": .05, "records": [
                {"case_name": "confirmation", "layout_seed": 580100,
                 "layout_parameters": {"xy_translation_m": [0., 0.]},
                 "state_sha256": "confirmed_state", "geometry_fingerprint": "confirmed_geometry",
                 "settled_moka_xy_m": [0., 0.], "permanent_training_exclusion": True}]}


@pytest.fixture
def layout():
    return {"layout_seed": 680100, "layout_parameters": {"xy_translation_m": [.08, 0.]},
            "state_sha256": "new_state", "geometry_fingerprint": "new_geometry",
            "settled_moka_xy_m": [.08, 0.]}


def test_rejects_a_new_seed_with_near_identical_settled_position(layout, registry):
    layout["settled_moka_xy_m"] = [.0499, 0.]
    with pytest.raises(ValueError, match="less than 5 cm"):
        check_training_layout(layout, registry)


def test_exact_five_centimetre_boundary(layout, registry):
    layout["settled_moka_xy_m"] = [.05, 0.]
    result = check_training_layout(layout, registry)
    assert result["minimum_moka_xy_distance_m"] == .05


def test_checks_every_confirmation_layout(layout, registry):
    second = copy.deepcopy(registry["records"][0])
    second.update(case_name="second", layout_seed=580101, settled_moka_xy_m=[.04, 0.])
    registry["records"].append(second)
    with pytest.raises(ValueError, match="second"):
        check_training_layout(layout, registry)


@pytest.mark.parametrize("field", ["layout_parameters", "state_sha256", "geometry_fingerprint"])
def test_far_position_cannot_reuse_other_confirmation_identities(layout, registry, field):
    layout[field] = copy.deepcopy(registry["records"][0][field])
    with pytest.raises(ValueError, match="confirmation identity"):
        check_training_layout(layout, registry)


def test_confirmation_seed_remains_excluded_even_if_geometry_changes(layout, registry):
    registry["records"][0]["layout_seed"] = layout["layout_seed"]
    with pytest.raises(ValueError, match="confirmation identity"):
        check_training_layout(layout, registry)


@pytest.mark.parametrize("seed", [580124, 680099, 690000])
def test_disjoint_training_seed_range(layout, registry, seed):
    layout["layout_seed"] = seed
    with pytest.raises(ValueError, match="registered range"):
        check_training_layout(layout, registry)


@pytest.mark.parametrize("position", [None, [], [float("nan"), 0.], [0., 0., .1]])
def test_missing_or_invalid_settled_position_is_rejected(layout, registry, position):
    registry["records"][0]["settled_moka_xy_m"] = position
    with pytest.raises((ValueError, TypeError)):
        check_training_layout(layout, registry)


def test_registered_file_hash_is_checked_before_use(tmp_path, layout, registry):
    path = tmp_path / "confirmations.json"
    raw = json.dumps(registry).encode()
    path.write_bytes(raw)
    reference = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    assert check_registered_training_layout(layout, reference)["training_allowed"]
    path.write_text("{}")
    with pytest.raises(ValueError, match="registry changed"):
        check_registered_training_layout(layout, reference)


def test_permanent_exclusion_cannot_be_disabled(layout, registry):
    registry["records"][0]["permanent_training_exclusion"] = False
    with pytest.raises(ValueError, match="remain excluded"):
        check_training_layout(layout, registry)


def official_registration(tmp_path, *, coverage_complete=True):
    registry = {"schema": "libero_official_confirmation_exclusions/1", "training_allowed": False,
                "coverage_complete": coverage_complete,
                "records": [{"episode": {"suite": "libero_90", "task": 19, "seed": 12},
                             "state_sha256": "confirmed", "permanent_training_exclusion": True}]}
    path = tmp_path / "original_confirmations.json"
    path.write_text(json.dumps(registry))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_original_confirmation_init_stays_excluded_when_serialization_hash_changes(tmp_path):
    state = {"episode": {"suite": "libero_90", "task": 19, "seed": 12},
             "state_sha256": "different_serialization"}
    with pytest.raises(ValueError, match="original confirmation"):
        check_registered_training_original_state(state, official_registration(tmp_path))


def test_confirmation_state_sha_stays_excluded_under_an_episode_alias(tmp_path):
    state = {"episode": {"suite": "libero_90", "task": 19, "seed": 13},
             "state_sha256": "confirmed"}
    with pytest.raises(ValueError, match="original confirmation"):
        check_registered_training_original_state(state, official_registration(tmp_path))


def test_distinct_original_state_can_be_checked_against_explicit_registration(tmp_path):
    state = {"episode": {"suite": "libero_90", "task": 19, "seed": 13},
             "state_sha256": "unreserved"}
    assert check_registered_training_original_state(state, official_registration(tmp_path))["training_allowed"]


def test_incomplete_registration_cannot_admit_an_otherwise_distinct_training_state(tmp_path):
    state = {"episode": {"suite": "libero_90", "task": 19, "seed": 13},
             "state_sha256": "unreserved"}
    result = check_registered_training_original_state(
        state, official_registration(tmp_path, coverage_complete=False))
    assert result["training_allowed"] is False
    assert result["registration_coverage_complete"] is False
