"""An existing image alone cannot establish decision-time synchronization."""

import pytest

from scripts.package_v6_libero_images import match_frame
from scripts.diagnose_v5_preaction_success import auc, outcome


def fixture():
    event = {"measurements": [{"source_step": 8}], "post_measurements": [{"source_step": 19}],
             "robot_measurement": {"eef_xyz": [0, 0, 1], "gripper_opening": .08},
             "post_robot_measurement": {"eef_xyz": [0, 0, 1.1], "gripper_opening": .02}}
    steps = {8: {"step_idx": 8, "state": {"robot0_eef_pos": [0, 0, 1.00000001], "robot0_gripper_qpos": [.04, -.04]}},
             19: {"step_idx": 19, "state": {"robot0_eef_pos": [0, 0, 1.1], "robot0_gripper_qpos": [.01, -.01]}}}
    return event, steps


def test_auxiliary_post_frame_is_not_action_pre_frame():
    event, steps = fixture()
    assert match_frame(event, steps, post=False)[0]["step_idx"] == 8
    assert match_frame(event, steps, post=True)[0]["step_idx"] == 19


def test_disagreeing_robot_pose_refuses_frame_even_if_it_exists():
    event, steps = fixture()
    steps[8]["state"]["robot0_eef_pos"][0] = .02
    with pytest.raises(ValueError, match="robot/frame mismatch"):
        match_frame(event, steps, post=False)


def test_explicit_capture_precedes_legacy_entity_source_heuristic():
    event, steps = fixture()
    event["decision_frame_step"] = 3
    with pytest.raises(ValueError, match="registered frame"):
        match_frame(event, steps, post=False)


def test_selection_confidence_cannot_override_physical_failure_label():
    event = {"answer": {"probabilities": {"C0": .99}},
             "receipt": {"tool": "grasp", "grasp_verified": False}}
    assert outcome(event) == (0, "grasp_verified")
    assert outcome({"receipt": {"tool": "articulate", "verification": "unverified"}})[0] is None


def test_auc_ties_and_class_absence():
    assert auc([0, 1], [.1, .9]) == 1
    assert auc([0, 1], [.5, .5]) == .5
    assert auc([1], [.9]) is None
