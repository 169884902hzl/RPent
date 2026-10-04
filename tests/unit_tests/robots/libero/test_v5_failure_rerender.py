from copy import deepcopy
from collections import Counter
from dataclasses import asdict

import pytest

from robots.libero.v5_state import Entity
from robots.libero.v5_verification import placement_verification_status
from scripts.rerender_v5_format118_20261002 import relabel_recorded_skill_failure, revised_receipt
from scripts.derive_v5_recorded_skill_failures import derive


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


@pytest.mark.parametrize("missing", ["first", "second", "occluded"])
def test_rerender_preserves_unverified_placement_when_visual_evidence_is_missing(missing):
    measured = Entity("e1", "cream cheese", (0., 0., .1), (-.02, -.02, .08), (.02, .02, .12),
                      visible=missing != "occluded")
    target = Entity("e2", "basket", (.3, .3, .1), (.2, .2, 0.), (.4, .4, .2))
    receipt = {"tool": "place", "executed": True, "verification": "unverified",
               "place_verified": False, "verification_rule": "strict_place/1-dev"}
    record = {"receipt": receipt, "verification_measurements": {
        "kind": "placement", "first": None if missing == "first" else asdict(measured),
        "second": None if missing == "second" else asdict(measured), "target": asdict(target),
        "opening": .08, "eef_xyz": (0., 0., .4), "interval_s": .4, "relation": "in"}}
    original = deepcopy(record)
    rebuilt = revised_receipt(record, Counter())
    assert rebuilt == receipt
    assert record == original


def test_visible_failed_placement_retains_failure_but_unknown_is_not_a_failure():
    measured = Entity("e1", "bowl", (0., 0., .1), (-.02, -.02, .08), (.02, .02, .12))
    assert placement_verification_status(False, measured, measured) == "failed"
    assert placement_verification_status(True, measured, measured) == "verified"
    assert placement_verification_status(None, measured, measured) == "unverified"


def test_explicit_new_rule_recomputes_old_visual_evidence_without_changing_source():
    bowl = Entity("e1", "bowl", (0., 0., .1), (-.02, -.02, .08), (.02, .02, .12))
    shell = Entity("e2", "microwave", (0., 0., .1), (-.1, -.1, 0.), (.1, .1, .2))
    record = {"receipt": {"tool": "place", "executed": True, "verification": "verified",
                          "place_verified": True, "verification_rule": "strict_place/1-dev"},
              "verification_measurements": {"kind": "placement", "first": asdict(bowl),
                  "second": asdict(bowl), "target": asdict(shell), "opening": .08,
                  "eef_xyz": (0., 0., .4), "interval_s": .4, "relation": "in"}}
    original = deepcopy(record)
    historical = revised_receipt(record, Counter())
    assert historical["place_verified"] is True
    rebuilt = revised_receipt(record, Counter(), placement_rule="strict_place/3-dev")
    assert rebuilt["place_verified"] is None
    assert rebuilt["verification"] == "unverified"
    assert rebuilt["verification_rule"] == "strict_place/3-dev"
    assert rebuilt["verification_reason"] == "interior_containment_not_measured"
    assert record == original


def test_explicit_rule_does_not_erase_a_real_precondition_failure():
    receipt = {"tool": "place", "verification": "failed", "place_verified": False,
               "failure_reason": "waypoint_not_reached"}
    assert revised_receipt({"receipt": receipt}, Counter(),
                           placement_rule="strict_place/3-dev") == receipt


def test_explicit_rule_marks_missing_visual_evidence_unknown():
    receipt = {"tool": "place", "verification": "verified", "place_verified": True,
               "verification_rule": "strict_place/1-dev"}
    rebuilt = revised_receipt({"receipt": receipt}, Counter(), placement_rule="strict_place/3-dev")
    assert rebuilt["place_verified"] is None
    assert rebuilt["verification"] == "unverified"
    assert rebuilt["verification_rule"] == "strict_place/3-dev"
    assert rebuilt["measurement_gap"] == "two_frame_evidence_missing"


@pytest.mark.parametrize("receipt", [
    {"tool": "place", "verification": "execution_error", "error": "target missing"},
    {"tool": "place", "verification": "failed", "failure_reason": "waypoint_not_reached"},
    {"tool": "place", "verification": "failed", "failure_reason": "held_verification_lost"},
    {"tool": "adjust_place", "executed": True, "verification": "failed",
     "regrasp_verified": False, "place_verified": False},
])
def test_rerender_keeps_observed_execution_failure_without_visual_placement_frames(receipt):
    assert revised_receipt({"receipt": receipt}, Counter()) == receipt


def test_failure_auxiliary_preserves_measured_state_and_action_outcome_parent():
    parent = {
        'question_type': 'action_outcome', 'domain': 'libero', 'stage': 'receipt',
        'scene_id': 'original/libero_goal/t4/init10', 'step': 0, 'seed': 10,
        'request': {'state': 'instruction move bowl\nreceipt grasp failed'},
        'label_evidence': {'executed_receipt': {'tool': 'grasp', 'verification': 'failed'}},
        'memory_variant': 'none',
    }
    original = deepcopy(parent)
    row = derive(parent)
    assert row['request']['state'] == parent['request']['state']
    assert row['judge'] == 'program_termination'
    assert row['option_names'][row['acceptable_actions'][0]] == 'skill_execution_failure'
    assert row['label_evidence']['scope'] == 'skill_attempt_not_episode_termination'
    assert parent == original


def called_skill(receipt):
    return {
        'question_type': 'action_outcome', 'domain': 'libero', 'stage': 'receipt',
        'scene_id': 'original/libero_goal/t4/init10', 'step': 0, 'seed': 10,
        'request': {'state': 'instruction move bowl\nreceipt grasp failed'},
        'label_evidence': {'executed_receipt': receipt},
        'format_repair': {'runtime_source_file': 'original/choices.jsonl',
                          'runtime_source_line': 1, 'source_request_sha256': 'a' * 64},
    }


def test_conditional_runtime_error_keeps_uncompleted_physical_execution():
    parent = called_skill({'tool': 'place', 'executed': False, 'verification': 'execution_error',
                           'error': 'RuntimeError: blocked waypoint'})
    original = deepcopy(parent)
    row = derive(parent, conditional=True)
    assert row['judge'] == 'program_termination'
    assert row['label_evidence']['executed_receipt']['executed'] is False
    assert row['label_evidence']['scope'] == 'called_skill_with_failed_receipt/1'
    assert set(row['option_names'].values()) == {'skill_execution_error', 'skill_execution_failure'}
    assert row['option_names'][row['acceptable_actions'][0]] == 'skill_execution_error'
    assert 'returned a failed receipt' in row['request']['questions']['action']['instructions']
    assert row['request']['state'] == parent['request']['state']
    assert parent == original


def test_conditional_visual_failure_points_to_actual_measurements():
    row = derive(called_skill({'tool': 'grasp', 'executed': True, 'verification': 'failed',
                              'grasp_verified': False, 'gripper_opening': .0475,
                              'measured_z_rise_cm': .68}), conditional=True)
    assert row['judge'] == 'measured_predicate'
    assert row['label_evidence']['verification_evidence']['measured_z_rise_cm'] == .68
    assert row['label_evidence']['receipt_source']['runtime_source_line'] == 1
    assert row['option_names'][row['acceptable_actions'][0]] == 'skill_execution_failure'


def test_conditional_failure_without_measured_evidence_is_excluded():
    assert derive(called_skill({'tool': 'grasp', 'executed': True,
                                'verification': 'failed'}), conditional=True) is None
    assert derive(called_skill({'tool': 'grasp', 'executed': True, 'verification': 'failed',
                                'grasp_verified': False, 'gripper_opening': .04,
                                'measured_z_rise_cm': float('nan')}), conditional=True) is None


def test_conditional_question_does_not_label_uncalled_or_successful_skill():
    assert derive(called_skill({'tool': 'ask_help', 'verification': 'failed',
                                'error': 'no help'}), conditional=True) is None
    assert derive(called_skill({'tool': 'grasp', 'executed': True,
                                'verification': 'verified'}), conditional=True) is None


def test_conditional_place_failure_uses_observed_servo_endpoint():
    parent = called_skill({'tool': 'place', 'executed': True, 'verification': 'failed',
                           'place_verified': False, 'failure_reason': 'waypoint_not_reached'})
    parent['label_evidence']['recorded_motion_evidence'] = [
        {'target_xyz': [0, 0, 1.1], 'final_eef_pos': [0, 0, 1.06],
         'final_dist_m': .04, 'steps_used': 80}]
    original = deepcopy(parent)
    row = derive(parent, conditional=True)
    assert row['judge'] == 'measured_predicate'
    assert row['option_names'][row['acceptable_actions'][0]] == 'skill_execution_failure'
    assert row['label_evidence']['verification_evidence']['kind'] == 'measured_waypoint_residual'
    assert row['request']['state'] == parent['request']['state']
    assert parent == original


def test_waypoint_message_without_consistent_measured_endpoint_is_not_a_label():
    parent = called_skill({'tool': 'place', 'executed': True, 'verification': 'failed',
                           'place_verified': False, 'failure_reason': 'waypoint_not_reached',
                           'failure_detail': 'servo residual 0.15 m'})
    assert derive(parent, conditional=True) is None
    parent['label_evidence']['recorded_motion_evidence'] = [
        {'target_xyz': [0, 0, 1.1], 'final_eef_pos': [0, 0, 1.1],
         'final_dist_m': .15, 'steps_used': 80}]
    assert derive(parent, conditional=True) is None
    parent['label_evidence']['recorded_motion_evidence'][0]['steps_used'] = 0
    assert derive(parent, conditional=True) is None
