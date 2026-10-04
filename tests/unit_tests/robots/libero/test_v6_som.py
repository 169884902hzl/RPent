"""Calibrated image projection must share training/runtime geometry."""

import io

import numpy as np
from PIL import Image
import pytest

from robots.libero.v6_som import measured_part_mask, project_bounds, render_marks, visible_box


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


def test_component_filter_removes_small_remote_speckle_and_preserves_reference():
    world = np.zeros((100, 100, 3))
    world[45:55, 45:55] = [0, 0, 1.1]
    world[40, 40] = [0, 0, 1.1]
    mask = (world[..., 2] > 0)
    original = mask.copy()
    assert visible_box([40, 40, 60, 60], entity(), world, mask) == ([40, 40, 55, 55], 101)
    assert visible_box([40, 40, 60, 60], entity(), world, mask,
                       visible_component_filter_v1=True) == ([45, 45, 55, 55], 100)
    assert np.array_equal(mask, original)


def test_component_filter_keeps_two_substantial_visible_regions():
    world = np.zeros((100, 100, 3))
    world[40:45, 40:45] = [0, 0, 1.1]
    world[50:55, 50:55] = [0, 0, 1.1]
    assert visible_box([40, 40, 60, 60], entity(), world,
                       visible_component_filter_v1=True) == ([40, 40, 55, 55], 50)


def test_render_component_filter_is_disabled_by_default():
    image = io.BytesIO()
    Image.new("RGB", (100, 100)).save(image, format="PNG")
    world = np.zeros((100, 100, 3))
    world[45:55, 45:55] = [0, 0, 1.1]
    world[40, 40] = [0, 0, 1.1]
    default = render_marks(image.getvalue(), calibration(), [entity()], world_map=world)
    disabled = render_marks(image.getvalue(), calibration(), [entity()], world_map=world,
                            visible_component_filter_v1=False)
    enabled = render_marks(image.getvalue(), calibration(), [entity()], world_map=world,
                           visible_component_filter_v1=True)
    assert default == disabled
    assert default[1]["marks"][0]["box_xyxy"] == [40, 40, 55, 55]
    assert enabled[1]["marks"][0]["box_xyxy"] == [45, 45, 55, 55]
    assert enabled[0] != default[0]


def test_drawer_reference_is_its_measured_parent_subset_not_the_whole_cabinet():
    from scripts.check_v6_som_masks import overlap

    parent = np.zeros((100, 100), dtype=bool)
    parent[10:90, 20:80] = True
    world = np.zeros((100, 100, 3))
    world[10:90, 20:80] = [0, 0, 1.5]
    world[60:90, 20:80] = [0, 0, 1.1]
    part = {**entity(), "id": "e19", "part_of": "e37"}
    subset = measured_part_mask(parent, part, world)
    assert subset.sum() == 1800 and not subset[:60].any()
    box = [20, 60, 80, 90]
    assert overlap(box, parent)["mask_iou"] == .375
    assert overlap(box, subset)["mask_iou"] == 1
    # Correcting the reference must not change the image rectangle.
    assert visible_box([0, 0, 100, 100], part, world, parent) == visible_box(
        [0, 0, 100, 100], part, world, subset)


def test_part_subset_rejects_background_and_invalid_depth_without_creating_mask_pixels():
    parent = np.ones((4, 4), dtype=bool)
    parent[0, 0] = False
    world = np.full((4, 4, 3), [0, 0, 1.1])
    world[1, 0] = np.nan
    world[1, 1] = 0
    world[1, 2] = [0, 0, 1.8]
    subset = measured_part_mask(parent, entity(), world)
    assert subset.sum() == 12
    assert not subset[0, 0] and not subset[1, :3].any()
    assert np.all(subset <= parent)


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
