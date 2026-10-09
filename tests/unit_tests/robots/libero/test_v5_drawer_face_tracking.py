"""Public correspondence separates camera motion from drawer translation."""

import numpy as np
import pytest

from robots.libero.v5_drawer_face_tracking import track_face


def images_and_maps(*, displacement=0., camera_pixel_shift=0):
    import cv2

    rng = np.random.default_rng(37)
    image = rng.integers(0, 256, (160, 160, 3), dtype=np.uint8)
    yy, xx = np.mgrid[:160, :160]
    world = np.stack(((xx - 80) / 800, np.full(xx.shape, .1), .94 + yy / 4000), axis=-1)
    transform = np.float32([[1, 0, camera_pixel_shift], [0, 1, 0]])
    after = cv2.warpAffine(image, transform, (160, 160))
    last = cv2.warpAffine(world, transform, (160, 160))
    last[:, :, 1] -= displacement
    measurement = {"moving": {"centre": [0., .1, .96]}, "outward_axis_xy": [0., -1.],
                   "current_part_bounds": {"lower": [-.11, .095, .935], "upper": [.11, .105, .985]}}
    return image, world, after, last, measurement


@pytest.mark.parametrize("displacement", [0., .04, -.08])
def test_tracks_physical_axial_translation_with_camera_motion(displacement):
    result = track_face(*images_and_maps(displacement=displacement, camera_pixel_shift=8))
    assert result["status"] == "measured"
    assert result["axial_displacement_m"] == pytest.approx(displacement, abs=.001)
    assert result["tracked_face_centre_m"][1] == pytest.approx(.1 - displacement, abs=.001)
    assert result["private_values_used"] is False


def test_texture_loss_and_missing_face_are_unmeasured():
    before, world, after, last, measurement = images_and_maps()
    assert track_face(np.zeros_like(before), world, after, last, measurement)["status"] == "unmeasured"
    assert track_face(before, world, after, last, {})["status"] == "unmeasured"


def test_texture_outside_measured_panel_does_not_seed_correspondences():
    before, world, after, last, measurement = images_and_maps()
    # The only textured pixels have depths outside the selected front plane.
    before[60:100, 60:100] = 128
    world[:, :, 1] = .3
    world[65:95, 65:95, 1] = .1
    result = track_face(before, world, after, last, measurement)
    assert result["status"] == "unmeasured"
    assert result["reason"] == "initial_face_texture_unmeasured"
