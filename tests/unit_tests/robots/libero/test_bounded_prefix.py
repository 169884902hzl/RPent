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
