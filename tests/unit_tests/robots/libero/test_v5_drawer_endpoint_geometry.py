"""Current measured planes must distinguish a moving drawer from its frame."""

import numpy as np
from dataclasses import replace

from robots.libero.v5_fixture_parts import measured_drawer_faces
from robots.libero.v5_state import Entity
from robots.libero.v5_verification import measured_fixture_endpoint


def fixture():
    parent = Entity("e1", "cabinet", (0, 0, 1.05), (-.1, -.1, .9), (.1, .1, 1.2))
    drawer = Entity("e2", "cabinet middle drawer", (0, .1, 1.05), (-.09, .1, 1.0),
                    (.09, .1, 1.1), part_of="e1")
    return parent, drawer


def cloud(extension=0, frame_drift=0):
    border = np.array([(x, .1 + frame_drift, z)
                       for x in np.r_[np.linspace(-.1, -.085, 10), np.linspace(.085, .1, 10)]
                       for z in np.linspace(.92, 1.18, 25)])
    drawer = np.array([(x, .1 + extension, z) for x in np.linspace(-.07, .07, 30)
                       for z in np.linspace(1.01, 1.09, 20)])
    handle = np.array([(x, .125 + extension, z) for x in np.linspace(-.05, .05, 25)
                       for z in np.linspace(1.04, 1.05, 4)])
    return np.concatenate([border, drawer, handle])


def measure(points, step):
    evidence, clouds = measured_drawer_faces(points, *fixture(), (0, 1, 0))
    return {**evidence, "source_step": step}, clouds


def test_measured_frame_stays_fixed_while_drawer_opens_and_closes():
    before, _ = measure(cloud(), 0)
    after, measured = measure(cloud(.08), 1)
    assert after["moving"] and after["frame"]
    verified, evidence = measured_fixture_endpoint(before, after, "open", drawer=True)
    assert verified is True and abs(evidence["measured_extension_cm"] - 8) < .01
    assert measured_fixture_endpoint(before, after, "close", drawer=True)[0] is False
    closed, _ = measure(cloud(.004), 2)
    assert measured_fixture_endpoint(after, closed, "close", drawer=True)[0] is True
    assert all(len(points) >= 30 for points in measured.values())


def test_missing_frame_and_handles_alone_do_not_verify_a_drawer():
    parent, drawer = fixture()
    handles = np.array([(x, .13, z) for x in np.linspace(-.05, .05, 25)
                        for z in np.linspace(1.04, 1.05, 4)])
    sample, _ = measure(handles, 1)
    assert sample["frame"] is None and sample["moving"] is None
    assert measured_fixture_endpoint(sample, sample, "open", drawer=True)[0] is None
    assert measured_drawer_faces(cloud(), parent, drawer, None)[0]["reason"] == "measured_part_or_front_axis_missing"


def test_a_moving_reference_cannot_certify_the_endpoint():
    before, _ = measure(cloud(), 0)
    after, _ = measure(cloud(.08, frame_drift=.018), 1)
    result, evidence = measured_fixture_endpoint(before, after, "open", drawer=True)
    assert result is None and evidence["reason"] == "reference_frame_not_stable"


def test_current_drawer_binding_rejects_the_larger_exposed_static_plane():
    parent, initial = fixture()
    extension = .13
    current = replace(initial, xyz=(0, .1 + extension, 1.05),
                      lower=(-.09, .1 + extension, 1.0),
                      upper=(.09, .1 + extension, 1.1), source_step=1)
    static = np.array([(x, .1, z) for x in np.linspace(-.08, .08, 60)
                       for z in np.linspace(1.005, 1.095, 40)])
    points = np.concatenate([cloud(extension), static])
    legacy, _ = measured_drawer_faces(points, parent, initial, (0, 1, 0))
    bound, measured = measured_drawer_faces(
        points, parent, initial, (0, 1, 0), moving_part=current)
    assert abs(legacy["moving"]["centre"][1] - .1) < .001
    assert abs(bound["moving"]["centre"][1] - .23) < .001
    assert bound["frame"] == legacy["frame"]
    assert (measured["moving"][:, 1] > .2).all()
    before, _ = measured_drawer_faces(cloud(), parent, initial, (0, 1, 0), moving_part=initial)
    assert measured_fixture_endpoint(
        {**before, "source_step": 0}, {**bound, "source_step": 1}, "open", drawer=True)[0] is True


def test_current_drawer_binding_does_not_substitute_an_adjacent_drawer():
    parent, drawer = fixture()
    for wrong in (replace(drawer, id="e3"), replace(drawer, visible=False),
                  replace(drawer, part_of="e9")):
        result, measured = measured_drawer_faces(
            cloud(.13), parent, drawer, (0, 1, 0), moving_part=wrong)
        assert result["reason"] == "current_selected_drawer_identity_missing"
        assert len(measured["moving"]) == 0


def test_missing_current_drawer_depth_does_not_fall_back_to_static_plane():
    parent, drawer = fixture()
    missing = replace(drawer, lower=(-.09, .3, 1.0), upper=(.09, .3, 1.1), source_step=1)
    result, measured = measured_drawer_faces(
        cloud(), parent, drawer, (0, 1, 0), moving_part=missing)
    assert result["frame"] is not None
    assert result["moving"] is None and len(measured["moving"]) == 0


def test_already_open_parent_bounds_do_not_exclude_the_actual_frame_or_closed_face():
    parent, drawer = fixture()
    measured_parent = replace(parent, upper=(.1, .26, 1.2))
    opened = replace(drawer, xyz=(0, .26, 1.05), lower=(-.09, .26, 1.),
                     upper=(.09, .26, 1.1))
    closed = replace(drawer, xyz=(0, .104, 1.05), lower=(-.09, .104, 1.),
                     upper=(.09, .104, 1.1), source_step=1)
    legacy, _ = measured_drawer_faces(cloud(.16), measured_parent, opened,
                                      (0, 1, 0), moving_part=opened)
    assert legacy['frame'] is None
    before, _ = measured_drawer_faces(cloud(.16), measured_parent, opened,
        (0, 1, 0), moving_part=opened, measured_bounds_depth=True)
    after, _ = measured_drawer_faces(cloud(.004), measured_parent, opened,
        (0, 1, 0), moving_part=closed, measured_bounds_depth=True)
    assert before['frame'] and before['moving'] and after['frame'] and after['moving']
    result, _ = measured_fixture_endpoint({**before, 'source_step': 0},
        {**after, 'source_step': 1}, 'close', drawer=True)
    assert result is True
    assert after['depth_search_source'] == 'perception_parent_bounds'
    no_depth, _ = measured_drawer_faces(np.empty((0, 3)), measured_parent, opened,
        (0, 1, 0), moving_part=closed, measured_bounds_depth=True)
    assert no_depth['frame'] is None and no_depth['moving'] is None
