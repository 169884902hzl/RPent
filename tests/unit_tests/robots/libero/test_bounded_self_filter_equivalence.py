"""A broad phase must preserve the original visual-shell membership exactly."""
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from robots.libero.bounded_self_filter import remove_visual_robot


@pytest.mark.parametrize('angle', [0., .23, 1.7])
def test_visual_prefilter_matches_full_cloud_kernel_at_box_and_hull_edges(monkeypatch, angle):
    lower, upper = np.array([-.05, -.03, -.07]), np.array([.05, .03, .07])
    equations = np.c_[np.r_[np.eye(3), -np.eye(3)], np.r_[-upper, lower]]
    fixed = np.eye(4)
    fixed[:3, 3] = [.2, -.1, .5]
    pose = fixed.copy()
    pose[:3, :3] = Rotation.from_rotvec([0., 0., angle]).as_matrix()
    world_rotation = Rotation.from_euler('xyz', [.3, -.6, .7]).as_matrix()
    offset = np.array([.2, .3, .9])
    screen = SimpleNamespace(world_offset=offset, world_rotation=world_rotation,
        nodes=[(fixed, np.array([0., 0., 1.]))], joints=[angle], reference={'path': 'fake.xml'})
    hulls = [(0, 'visual', lower, upper, equations)]
    monkeypatch.setattr('robots.libero.bounded_self_filter.visual_hulls', lambda _: hulls)
    local = np.random.default_rng(717).uniform(-1., 1., (30000, 3))
    # Include exact and adjacent floating-point boundary values after
    # rotation, not only ordinary points far from the filter boundary.
    corners = np.array(np.meshgrid(*zip(lower-.004, upper+.004), indexing='ij')).reshape(3, -1).T
    local = np.concatenate([local, corners, np.nextafter(corners, np.inf),
                            np.nextafter(corners, -np.inf)])
    base = local@pose[:3, :3].T+pose[:3, 3]
    cloud = base@world_rotation.T+offset
    measured_base = (cloud-offset)@world_rotation
    measured_local = (measured_base-pose[:3, 3])@pose[:3, :3]
    old_ids = np.flatnonzero(((measured_local >= lower-.004)&(measured_local <= upper+.004)).all(1))
    removed = np.zeros(len(cloud), bool)
    for batch in np.array_split(old_ids, max(1, (len(old_ids)+255)//256)):
        inside = (measured_local[batch]@equations[:, :3].T+equations[:, 3] <= .004).all(1)
        removed[batch[inside]] = True
    actual, evidence = remove_visual_robot(cloud, screen)
    np.testing.assert_array_equal(actual, cloud[~removed])
    assert evidence['removed_points'] == int(removed.sum())
    assert evidence['per_mesh'] == {'visual': int(removed.sum())}
