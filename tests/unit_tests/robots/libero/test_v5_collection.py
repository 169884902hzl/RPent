"""Collection labels need tested outcomes and the instruction's progress."""

from robots.libero.v5_collection import accepted_branch
from robots.libero.v5_state import Candidate


def test_premature_finish_is_negative_even_when_finish_executed():
    before = {"done": False, "satisfied": [False]}
    assert accepted_branch(Candidate("finish"), {"executed": True}, before, before) is False
    done = {"done": True, "satisfied": [True]}
    assert accepted_branch(Candidate("finish"), {"executed": True}, done, done) is True
    assert accepted_branch(Candidate("ask_help"), {"executed": True}, done, done) is False


def test_verified_wrong_destination_is_not_an_acceptable_task_action():
    before = {"done": False, "satisfied": [False]}
    place = Candidate("place", "e1", "e2", "in")
    assert accepted_branch(place, {"place_verified": True}, before, before) is False
    after = {"done": True, "satisfied": [True]}
    assert accepted_branch(place, {"place_verified": True}, before, after) is True


def test_an_executed_grasp_does_not_imply_verified_grasp():
    status = {"done": False, "satisfied": [False]}
    action = Candidate("grasp", "e1", mode="direct")
    assert accepted_branch(action, {"executed": True}, status, status, required_objects={"e1"}) is False
    assert accepted_branch(action, {"grasp_verified": True}, status, status, required_objects={"e1"}) is True
    assert accepted_branch(action, {"grasp_verified": True}, status, status, required_objects={"e2"}) is None


def test_completed_physical_goal_and_grasp_verification_are_separate():
    before = {"done": False, "satisfied": [False]}
    after = {"done": True, "satisfied": [True]}
    assert accepted_branch(Candidate("grasp", "e1", mode="direct"),
                           {"executed": True, "grasp_verified": False}, before, after,
                           required_objects={"e1"}) is True


def test_physical_container_progress_survives_failed_visual_above_rim_check():
    before = {"done": False, "satisfied": [False, False]}
    after = {"done": False, "satisfied": [True, False]}
    action = Candidate("place", "e1", "e2", "in")
    receipt = {"executed": True, "verification": "failed", "place_verified": False}
    assert accepted_branch(action, receipt, before, after) is True
    regress_before = {"done": False, "satisfied": [True, False]}
    regress_after = {"done": False, "satisfied": [False, True]}
    assert accepted_branch(action, receipt, regress_before, regress_after) is False


def test_storage_prerequisite_open_is_acceptable_and_early_close_is_not():
    closed = {"done": False, "goals": [["close", "drawer"], ["in", "bowl", "drawer"]],
              "satisfied": [True, False], "storage_open": {"drawer": False}}
    opened = {**closed, "satisfied": [False, False], "storage_open": {"drawer": True}}
    receipt = {"executed": True, "verification": "unverified"}
    assert accepted_branch(Candidate("articulate", "e2", mode="open"), receipt, closed, opened) is True
    assert accepted_branch(Candidate("articulate", "e2", mode="close"), receipt, opened, closed) is False
