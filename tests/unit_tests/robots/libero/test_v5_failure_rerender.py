from copy import deepcopy

from scripts.rerender_v5_format118_20261002 import relabel_recorded_skill_failure


def skill_failure_row():
    return {
        'option_names': {'C0': 'skill_execution_error', 'C1': 'skill_execution_failure',
                         'C2': 'perception_missing_object'},
        'request': {'state': 'instruction move the bowl\nreceipt grasp failed'},
        'label_evidence': {'kind': 'programmatic_receipt_reason',
                           'scope': 'skill_attempt_not_episode_termination'},
    }


def test_skill_error_remains_error_when_later_episode_completes():
    row = skill_failure_row()
    state = deepcopy(row['request'])
    receipt = {'tool': 'place', 'verification': 'execution_error', 'error': 'ValueError: target missing'}
    assert relabel_recorded_skill_failure(row, receipt)
    assert row['acceptable_actions'] == ['C0']
    assert row['target'] == {'C0': 1., 'C1': 0., 'C2': 0.}
    assert 'termination_category' not in row['label_evidence']
    assert row['request'] == state


def test_measured_physical_failure_is_separate_from_python_exception():
    row = skill_failure_row()
    assert relabel_recorded_skill_failure(row, {'tool': 'grasp', 'verification': 'failed',
                                               'grasp_verified': False})
    assert row['acceptable_actions'] == ['C1']
    assert row['label_evidence']['scope'] == 'skill_attempt_not_episode_termination'


def test_missing_strict_verification_does_not_receive_invented_failure_label():
    row = skill_failure_row()
    original = deepcopy(row)
    assert not relabel_recorded_skill_failure(row, {'tool': 'place', 'verification': 'unverified',
                                                   'measurement_gap': 'two_frame_evidence_missing'})
    assert row == original
