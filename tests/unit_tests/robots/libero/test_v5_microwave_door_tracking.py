"""Identity must come from current RGB-D correspondence, never a front hint."""

import numpy as np
import pytest

from robots.libero.v5_microwave_identity import track_measured_door


def translated_public_panel():
    import cv2
    rng = np.random.default_rng(7)
    image = np.zeros((160, 200, 3), np.uint8)
    image[20:140, 30:150] = rng.integers(0, 256, (120, 120, 3), dtype=np.uint8)
    moved = cv2.warpAffine(image, np.float32([[1, 0, 5], [0, 1, 0]]), (200, 160))
    mask = np.zeros((160, 200), bool)
    mask[25:135, 35:145] = True
    rows, columns = np.mgrid[:160, :200]
    world = np.stack((columns * .002, np.full_like(rows, .25, dtype=float), 1 + rows * .002), axis=-1)
    anchor = {"lower": [.5, .24, .9], "upper": [.6, .26, 1.4], "source_step": 0}
    return image, moved, world.astype(np.float16), world.astype(np.float16), mask, anchor


def test_float16_public_depth_tracks_a_translated_independent_panel():
    mask, plane, evidence = track_measured_door(*translated_public_panel())
    assert plane is not None
    assert mask.sum() >= 60
    assert evidence["rigid_fraction"] >= .55
    assert evidence["plane_support_fraction_of_rigid_tracks"] >= .55
    assert evidence["private_labels_used"] is False
    assert evidence["stop_admitted"] is False


@pytest.mark.parametrize("missing", ["initial_identity", "visual_texture", "depth", "robot_occlusion"])
def test_lost_public_support_cannot_be_replaced_with_an_appliance_plane(missing):
    image, moved, previous, current, mask, anchor = translated_public_panel()
    robot = None
    if missing == "initial_identity":
        mask[:] = False
    elif missing == "visual_texture":
        image[:] = moved[:] = 0
    elif missing == "depth":
        current[:] = 0
    else:
        robot = np.ones(mask.shape, bool)
    mask, plane, evidence = track_measured_door(image, moved, previous, current, mask, anchor, robot_mask=robot)
    assert plane is None
    assert not mask.any()
    assert evidence["stop_admitted"] is False
