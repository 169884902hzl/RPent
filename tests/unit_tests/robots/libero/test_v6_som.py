"""Calibrated image projection must share training/runtime geometry."""

import io

import numpy as np
from PIL import Image
import pytest

from robots.libero.v6_som import project_bounds, render_marks


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
