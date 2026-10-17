"""Never diagnose a different physical prefix after silently losing controls."""
import pytest

from scripts.probe_bounded_prefix_diagnostic import prefix_controls


def test_preparation_and_contact_controls_both_belong_to_the_prefix():
    sample = {'action': [0., 0., 0., 0., 0., 0., 1.]}
    rows = [{'index': 0, 'sim_steps_before': 0, 'sim_steps_after': 3,
        'execution_details': [{'execution': {'preparation': {'trace': [sample]},
                                           'trace': [sample, sample]}}]}]
    assert len(prefix_controls(rows, 0)) == 3


def test_old_gripper_rows_without_saved_controls_are_rejected():
    rows = [{'index': 2, 'sim_steps_before': 100, 'sim_steps_after': 115,
             'execution_details': [{'execution': {}}]}]
    with pytest.raises(ValueError, match='incomplete controls at row 2: 0 != 15'):
        prefix_controls(rows, 0)


def test_missing_prefix_row_is_rejected():
    with pytest.raises(ValueError, match='row does not exist'):
        prefix_controls([], 0)


def test_private_pixel_identity_flip_and_isolation():
    from types import SimpleNamespace

    import numpy as np

    from robots.libero.v5_motion_diagnostics import pixel_geometry_diagnostic

    raw = np.array([[[5, 0]], [[5, 1]]])
    model = SimpleNamespace(ngeom=2, geom_id2name=lambda i: ('hand', 'handle')[i])
    wrapper = SimpleNamespace(env=SimpleNamespace(sim=SimpleNamespace(
        model=model, render=lambda **kwargs: raw)))
    result = pixel_geometry_diagnostic(wrapper, 'agentview', 2, 1)
    np.testing.assert_array_equal(result['segmentation'], raw[::-1])
    assert result['geom_names'] == {'0': 'hand', '1': 'handle'}
    assert result['source'] == 'simulation_pixel_geometry_diagnostic_only'
    with pytest.raises(ValueError, match='recorded LIBERO view'):
        pixel_geometry_diagnostic(wrapper, 'arbitrary', 2, 1)
