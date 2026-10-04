"""Calibrated image projection must share training/runtime geometry."""

import io

import numpy as np
from PIL import Image
import pytest

from robots.libero.v6_som import project_bounds, render_marks, visible_box


def calibration():
    return {"width": 100, "height": 100, "intrinsic_K": [[100, 0, 50], [0, 100, 50], [0, 0, 1]],
            "extrinsic_cam2world": np.eye(4).tolist()}


def entity(lower=(-.1, -.1, 1), upper=(.1, .1, 1.2)):
    return {"id": "e37", "lower": lower, "upper": upper, "src": "perception"}


def test_calibration_resolution_scales_both_axes():
    assert project_bounds(entity(), calibration(), (100, 100)) == [40, 40, 60, 60]
    assert project_bounds(entity(), calibration(), (400, 200)) == [160, 80, 240, 120]


def test_camera_pose_uses_inverse_world_transform():
    meta = calibration()
    meta["extrinsic_cam2world"][0][3] = 1
    assert project_bounds(entity((.9, -.1, 1), (1.1, .1, 1.2)), meta, (100, 100)) == [40, 40, 61, 60]


def test_offscreen_and_behind_camera_are_omitted():
    assert project_bounds(entity((2, 0, 1), (3, 1, 2)), calibration(), (100, 100)) is None
    assert project_bounds(entity((-.1, -.1, -2), (.1, .1, -1)), calibration(), (100, 100)) is None


def test_near_plane_crossing_is_clipped_without_mirroring():
    assert project_bounds(entity((-.1, -.1, -.1), (.1, .1, .1)), calibration(), (100, 100)) == [0, 0, 100, 100]


def test_truth_geometry_and_internal_ids_rejected():
    with pytest.raises(ValueError, match="simulator"):
        project_bounds({**entity(), "src": "sim_truth"}, calibration(), (100, 100))
    with pytest.raises(ValueError, match="public"):
        project_bounds({**entity(), "id": "obj_1"}, calibration(), (100, 100))


def test_render_retains_public_binding_and_valid_png():
    original = io.BytesIO()
    Image.new("RGB", (100, 100)).save(original, format="PNG")
    marked, detail = render_marks(original.getvalue(), calibration(), [entity()])
    assert detail["marks"][0]["id"] == "e37"
    assert Image.open(io.BytesIO(marked)).size == (100, 100)


def test_old_measured_volume_with_no_current_depth_support_has_no_mark():
    world = np.zeros((100, 100, 3))
    assert visible_box([40, 40, 60, 60], entity(), world) == (None, 0)


def test_current_depth_support_tightens_projection_without_using_semantic_mask():
    world = np.zeros((100, 100, 3))
    world[45:50, 42:53] = [0, 0, 1.1]
    box, count = visible_box([40, 40, 60, 60], entity(), world)
    assert box == [42, 45, 53, 50]
    assert count == 55


def test_view_mask_prevents_a_mark_from_using_neighboring_depth():
    world = np.zeros((100, 100, 3))
    world[42:60, 40:60] = [0, 0, 1.1]
    mask = np.zeros((100, 100), dtype=bool)
    mask[45:50, 42:53] = True
    assert visible_box([40, 40, 60, 60], entity(), world, mask) == ([42, 45, 53, 50], 55)


def test_current_instance_masks_are_saved_with_frame_and_content_hash(tmp_path):
    from types import SimpleNamespace
    import hashlib
    from robots.libero.v5_runtime import MeasuredScene
    from rpent.session.base import EnvState

    state = EnvState(tmp_path)
    scene = SimpleNamespace(toolkit=SimpleNamespace(_state=state))
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:8, 3:9] = True
    with state.record_step(state={}) as step:
        record = MeasuredScene.save_sam_mask(scene, mask, "wrist")
    assert record["source_step"] == step == 0
    assert record["sha256"] == hashlib.sha256(open(record["path"], "rb").read()).hexdigest()
    with np.load(record["path"]) as stored:
        assert np.array_equal(stored["array"], mask)


def test_mask_check_rejects_other_camera_frame_and_modified_file(tmp_path):
    import hashlib
    from scripts.check_v6_som_masks import load_measurement_mask

    path = tmp_path / "mask.npz"
    mask = np.ones((8, 9), dtype=bool)
    np.savez_compressed(path, array=mask)
    record = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "camera": "wrist", "source_step": 4}
    assert np.array_equal(load_measurement_mask(record, view="wrist", step=4), mask)
    with pytest.raises(ValueError, match="another view or frame"):
        load_measurement_mask(record, view="agentview", step=4)
    with pytest.raises(ValueError, match="another view or frame"):
        load_measurement_mask(record, view="wrist", step=5)
    np.savez_compressed(path, array=~mask)
    with pytest.raises(ValueError, match="mask changed"):
        load_measurement_mask(record, view="wrist", step=4)
