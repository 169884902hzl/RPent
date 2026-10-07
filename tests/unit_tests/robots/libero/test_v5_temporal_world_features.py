import numpy as np
from PIL import Image

from robots.libero.v5_temporal_verifier import feature_encoder_identity, frame_features, infer
from robots.libero.v5_temporal_world_features import pool_view


BOUNDS = {"lower": [0., 0., 0.], "upper": [1., 1., 1.]}


def public_view(tmp_path, name, permutation=None):
    yy, xx = np.meshgrid(np.linspace(.01, .99, 16), np.linspace(.01, .99, 8), indexing="ij")
    points = np.stack([xx, yy, np.full_like(xx, .4)], axis=-1).reshape(-1, 3)
    colors = np.round(np.stack([xx, yy, np.full_like(xx, .7)], axis=-1) * 255).astype(np.uint8).reshape(-1, 3)
    if permutation is not None:
        points, colors = points[permutation], colors[permutation]
    rgb, world = tmp_path / f"{name}.png", tmp_path / f"{name}.npz"
    Image.fromarray(colors.reshape(16, 8, 3)).save(rgb)
    np.savez_compressed(world, array=points.reshape(16, 8, 3))
    return {"raw_rgb": {"path": str(rgb)}, "raw_world": {"path": str(world)}}


def test_world_grid_keeps_correspondence_when_camera_pixels_move(tmp_path):
    original = public_view(tmp_path, "initial")
    moved = public_view(tmp_path, "wrist_moved", np.random.default_rng(57).permutation(128))
    first, valid_first = pool_view(original, BOUNDS)
    second, valid_second = pool_view(moved, BOUNDS)
    assert valid_first and valid_second
    np.testing.assert_allclose(first, second, atol=1e-6)
    crop_first, _ = frame_features({"views": {"wrist": original}}, BOUNDS)
    crop_second, _ = frame_features({"views": {"wrist": moved}}, BOUNDS)
    assert not np.allclose(crop_first, crop_second)


def test_profile_keeps_missing_camera_mask(tmp_path):
    view = public_view(tmp_path, "agent")
    values, available = frame_features({"views": {"agentview": view}}, BOUNDS, profile="world_xy_grid_v1")
    assert values.shape == (640,) and available == [True, False]
    np.testing.assert_array_equal(values[320:], np.zeros(320))


def test_missing_or_invalid_measurement_cannot_create_features(tmp_path):
    view = public_view(tmp_path, "agent")
    for candidate, bounds in (({}, BOUNDS), (view, {"lower": [0., 0., np.nan], "upper": [1., 1., 1.]})):
        values, available = pool_view(candidate, bounds)
        assert not available and not values.any()


def test_model_cannot_consume_another_encoder_profile(tmp_path):
    path = tmp_path / "model.npz"
    np.savez(path, supports_modes=np.asarray(["turn_off"]), encoder_profile=np.asarray("world_xy_grid_v1"),
             feature_encoder_sha256=np.asarray(feature_encoder_identity(profile="world_xy_grid_v1")))
    result = infer(np.zeros(2578), [True, True], path, threshold=.7, requested_mode="turn_off")
    assert result["reason"] == "temporal_encoder_profile_mismatch"
    assert result["stop_admitted"] is False and result["p_satisfied"] is None
