"""Shared capture quantisation preserves exact original-pixel membership."""
import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_obstacles import build_obstacles, subtract_instances
from robots.libero.v5_grasp_route import separate_target_points


def test_shared_partition_keeps_next_surviving_pixel_in_target_voxel():
    rng = np.random.default_rng(321)
    points = rng.uniform(-.06, .06, (10000, 3))
    points = np.concatenate([points, points[:300], points[:300]+[.0002, 0, 0]])
    structure = build_obstacles(points)
    for target, held in [(points[:350], np.empty((0, 3))),
                         (points[800:1200], points[1400:1410]),
                         (np.empty((0, 3)), np.empty((0, 3)))]:
        baseline = points
        if len(held):
            baseline = baseline[cKDTree(held).query(baseline,
                distance_upper_bound=np.nextafter(.012, np.inf))[0] > .012]
        _, expected = separate_target_points(np.concatenate([target, held]), baseline)
        actual = subtract_instances(structure, target, held, held_margin_m=.012)
        assert np.array_equal(actual, expected)
        assert subtract_instances(structure, target, held, held_margin_m=.012) is actual


def test_exact_instance_tolerance_does_not_remove_neighbouring_obstacles():
    points = np.array([[.1, .1, .1], [.1000005, .1, .1], [.100002, .1, .1],
                       [.2, .2, .2]])
    target = points[:1]
    actual = subtract_instances(build_obstacles(points), target, np.empty((0, 3)), held_margin_m=.012)
    assert np.array_equal(actual, points[[2, 3]])
