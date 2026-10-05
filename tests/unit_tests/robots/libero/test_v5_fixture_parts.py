"""Partial current depth must retain measured cabinet layer identities."""

import numpy as np

from robots.libero.v5_fixture_parts import fixture_parts, measured_handle_front
from robots.libero.v5_state import Entity


def test_microwave_shell_is_not_promoted_to_a_measured_moving_door():
    # The 3655 original scene had a nonplanar 59,695-point shell cloud. The
    # generic cabinet-front flag nevertheless advertised its entire bounds
    # as a measured door. Multiple appliance walls are not independent door
    # evidence, regardless of which side is currently visible.
    appliance = Entity("e9", "microwave", (0, 0, 1), (-.15, -.15, .9), (.15, .15, 1.15))
    cloud = np.array([(x, y, z) for x in np.linspace(-.15, .15, 20)
                      for y in (-.15, .15) for z in np.linspace(.9, 1.15, 20)])
    assert fixture_parts(appliance, cloud, (1, 0, 0), calibrated_front=True) == []
    assert fixture_parts(appliance, cloud, (1, 0, 0), calibrated_front=False) == []


def cabinet():
    return Entity("e1", "cabinet", (0, 0, 1.0), (-.12, -.08, .9), (.12, .08, 1.11))


def front(zlo, zhi):
    return np.array([(x, .08, z) for x in np.linspace(-.1, .1, 20)
                     for z in np.linspace(zlo, zhi, 20)])


def test_an_occluded_lower_fragment_does_not_become_the_top_surface():
    parts = fixture_parts(cabinet(), front(.905, .955), (0, 1, 0), calibrated_front=True)
    assert [part["name"] for part in parts] == ["cabinet bottom drawer"]
    assert parts[0]["upper"][2] <= .955


def test_current_middle_face_keeps_its_layer_when_other_layers_are_missing():
    parts = fixture_parts(cabinet(), front(.975, 1.03), (0, 1, 0), calibrated_front=True)
    assert [part["name"] for part in parts] == ["cabinet middle drawer"]


def test_dense_horizontal_roof_does_not_displace_the_top_drawer_centre():
    roof = np.array([(x, y, 1.11) for x in np.linspace(-.12, .12, 80)
                     for y in np.linspace(-.08, .08, 80)])
    cloud = np.concatenate([front(1.045, 1.095), roof])
    parts = fixture_parts(cabinet(), cloud, (0, 1, 0), calibrated_front=True)
    drawer = next(part for part in parts if part["name"] == "cabinet top drawer")
    top = next(part for part in parts if part["name"] == "cabinet top surface")
    assert drawer["xyz"][2] < 1.10 and drawer["upper"][2] <= 1.095
    assert top["xyz"][2] == 1.11


def test_handle_alone_cannot_supply_a_drawer_face():
    cloud = np.array([(x, .105, z) for x in np.linspace(-.06, .06, 30)
                      for z in np.linspace(.925, .93, 10)])
    assert fixture_parts(cabinet(), cloud, (0, 1, 0), calibrated_front=True) == []


def test_closed_repeated_handle_rows_establish_front_but_one_row_does_not():
    rows = [np.array([(x, .11, z) for x in np.linspace(-.06, .06, 40)
                      for z in np.linspace(height, height + .008, 5)])
            for height in (.925, .995, 1.065)]
    assert measured_handle_front(np.concatenate(rows), cabinet())[0] == (0., 1., 0.)
    assert measured_handle_front(rows[0], cabinet())[0] is None


def test_opposite_visible_handle_profiles_remain_ambiguous():
    rows = np.array([(x, y, z) for x in np.linspace(-.06, .06, 40)
                     for y in (-.11, .11) for height in (.925, .995, 1.065)
                     for z in np.linspace(height, height + .008, 5)])
    assert measured_handle_front(rows, cabinet())[0] is None


def test_missing_current_depth_does_not_reuse_the_parent_pose_as_a_part():
    assert fixture_parts(cabinet(), np.empty((0, 3)), (0, 1, 0), calibrated_front=True) == []
