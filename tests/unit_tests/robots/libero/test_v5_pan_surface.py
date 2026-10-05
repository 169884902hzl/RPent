"""A rim hypothesis must not silently become a measured support footprint."""

import math

import numpy as np
import pytest

from robots.libero.v5_pan_surface import (
    disk_rectangle_fraction,
    maximum_disk_rectangle_fraction,
    observed_radial_layers,
)


def test_disk_area_differs_from_its_bbox_coverage():
    fraction = disk_rectangle_fraction((0, 0), .1, (-.09, -.09), (.09, .09))
    assert fraction > .9
    assert fraction > .18 ** 2 / .2 ** 2
    # Moving a measured body off the centre is not repaired by excluding a handle.
    assert disk_rectangle_fraction((0, .065), .1, (-.09, -.09), (.09, .09)) < .7


def test_exact_inside_and_outside_cases():
    assert disk_rectangle_fraction((0, 0), .1, (-1, -1), (1, 1)) == pytest.approx(1, abs=1e-6)
    assert disk_rectangle_fraction((0, 0), .1, (1, 1), (2, 2)) == 0
    assert disk_rectangle_fraction((0, 0), 1, (-.1, -.1), (.1, .1)) == pytest.approx(.04 / math.pi)


def test_best_centred_disk_fraction_is_not_a_support_verdict():
    maximum = maximum_disk_rectangle_fraction(.102, (-.09, -.09), (.09, .09))
    assert .90 < maximum < .95
    assert disk_rectangle_fraction((.04, 0), .102, (-.09, -.09), (.09, .09)) < maximum
    with pytest.raises(ValueError):
        disk_rectangle_fraction((0, 0), 0, (-1, -1), (1, 1))


def test_visible_inner_floor_and_low_band_remain_contact_unknown():
    angles = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    inner = np.c_[.07 * np.cos(angles), .07 * np.sin(angles), np.zeros(100)]
    rim = np.c_[.1 * np.cos(angles), .1 * np.sin(angles), np.full(100, .02)]
    cloud = np.r_[inner, rim, [[np.nan, 0, 0]]]
    profile = observed_radial_layers(cloud, plane_origin=(0, 0, 0),
        plane_normal=(0, 0, 1), body_centre=(0, 0, 0), radius_m=.1,
        camera_origin=(0, 0, 1))
    assert profile["finite_points"] == 200
    assert profile["observed_low_band"]["points"] == 100
    assert profile["camera_signed_plane_distance_m"] == 1
    assert profile["support_footprint"] is None
    assert "hidden_bottom_contact" in profile["reason"]


def test_no_observation_does_not_complete_an_unseen_disk():
    profile = observed_radial_layers(np.empty((0, 3)), plane_origin=(0, 0, 0),
        plane_normal=(0, 0, 1), body_centre=(0, 0, 0), radius_m=.1,
        camera_origin=(0, 0, 1))
    assert profile["support_footprint"] is None
    assert profile["reason"] == "no_finite_public_points"
