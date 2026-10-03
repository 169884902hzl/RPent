"""Support must come from the foreground plane, not a same-height background."""

import numpy as np

from robots.libero.v5_perception_geometry import measured_work_surface, microwave_geometry_supported
from robots.libero.v5_state import Entity


def test_connected_plane_is_selected_by_measured_object_neighborhood():
    world = np.zeros((100, 150, 3))
    y, x = np.mgrid[0:100, 0:70]
    world[:, :70] = np.stack((-1.5 + x * .003, y * .004 - .2, np.full_like(x, .9, dtype=float)), axis=-1)
    y, x = np.mgrid[0:100, 0:70]
    world[:, 80:] = np.stack((x * .003 - .1, y * .004 - .2, np.full_like(x, .9, dtype=float)), axis=-1)
    mug = Entity("e1", "mug", (0, 0, .97), (-.04, -.04, .916), (.04, .04, 1.04))
    surface = measured_work_surface(world, [mug])
    assert surface is not None and surface["lower"][0] > -.11
    assert abs(surface["height_m"] - .9) <= .002
    assert surface["points"] == 7000
    assert microwave_geometry_supported((-.05, .1, .92), (.25, .25, 1.15), surface)
    assert not microwave_geometry_supported((-1.5, .1, .92), (-1.2, .25, 1.15), surface)
    assert not microwave_geometry_supported((-.1, -.1, .92), (-.09, .2, 1.15), surface)


def test_no_nearby_support_or_ambiguous_surfaces_remain_unmeasured():
    assert measured_work_surface(np.zeros((10, 10, 3)), []) is None
    mug = Entity("e1", "mug", (2, 2, 1), (1.95, 1.95, .916), (2.05, 2.05, 1.04))
    world = np.zeros((100, 100, 3))
    y, x = np.mgrid[0:100, 0:100]
    world[:] = np.stack((x * .004, y * .004, np.full_like(x, .9, dtype=float)), axis=-1)
    assert measured_work_surface(world, [mug]) is None


def test_compound_door_and_table_is_not_a_measured_appliance_volume():
    from robots.libero.v5_perception_geometry import appliance_foreground_mask, measured_points

    world = np.zeros((50, 50, 3))
    y, x = np.mgrid[:50, :50]
    world[:] = np.stack((-.4 + x * .006, y * .006, np.full_like(x, .9, dtype=float)), axis=-1)
    world[:30] = np.stack((np.full((30, 50), -.18), x[:30] * .005,
                           .93 + y[:30] * .006), axis=-1)
    mask = np.ones((50, 50), dtype=bool)
    before = measured_points(world, mask)
    surface = {"height_m": .9, "lower": [-.5, -.5, .9], "upper": [.5, .5, .9]}
    assert microwave_geometry_supported(*np.quantile(before, (.02, .98), axis=0), surface)
    filtered, detail = appliance_foreground_mask(world, mask, surface)
    after = measured_points(world, filtered)
    assert detail["retained_points"] == 1500
    assert not microwave_geometry_supported(*np.quantile(after, (.02, .98), axis=0), surface)


def test_query_overlap_resolves_duplicate_appliance_despite_biased_medians():
    from robots.libero.v5_perception_geometry import same_segmented_instance

    first = np.zeros((60, 60), dtype=bool)
    first[10:50, 10:40] = True
    second = first.copy()
    second[10:50, 40:50] = True
    distinct = np.zeros_like(first)
    distinct[10:50, 50:60] = True
    assert same_segmented_instance(first, second)
    assert not same_segmented_instance(first, distinct)
    assert not same_segmented_instance(first, np.zeros_like(first))
