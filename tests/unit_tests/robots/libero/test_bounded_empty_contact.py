"""Missing contact samples must not fabricate a surface or abort planning."""
import numpy as np
import pytest
from tests.unit_tests.robots.libero.test_bounded_skills import adapter


@pytest.mark.parametrize('active', [None, 'e1'])
@pytest.mark.parametrize('current_visible', [False, True])
def test_empty_committed_surface_keeps_only_current_instance(adapter, active, current_visible):
    current = np.array([[.1, .1, .9]]) if current_visible else np.empty((0, 3))
    adapter._instance_pixels = lambda _: current.copy()
    adapter.active = active
    adapter.committed_grasps['e1'] = {'anchor_xyz': np.array([.1, .1, .9])}
    adapter.plans['e1'] = {'surface_measurement': {'xyz_world': np.empty((0, 3)), 'source_step': 0}}
    np.testing.assert_array_equal(adapter._contact_pixels('e1'), current)
