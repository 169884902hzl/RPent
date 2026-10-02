"""Physical completion does not replace the required explicit finish choice."""

from harness_v5_eval import _termination_category
from robots.libero.v5_state import Candidate


def test_physical_success_without_finish_retains_budget_termination():
    category, detail = _termination_category(
        {"status": "completed", "official_success": True, "native_truncated": False},
        Candidate("place", "e1", "e2", "on"),
        {"place_verified": True}, None, loop_exhausted=True,
    )
    assert category == "budget_exhausted"
    assert detail == "decision_or_episode_budget"


def test_finish_keeps_independent_correct_and_false_completion_evidence():
    for solved, detail in ((True, "correct_completion"), (False, "false_finish")):
        assert _termination_category(
            {"status": "completed", "official_success": solved},
            Candidate("finish"), {"executed": True}, None, loop_exhausted=False,
        ) == ("completion_judgment", detail)


def test_model_help_without_private_binding_cannot_claim_missing_perception():
    category, detail = _termination_category(
        {"status": "completed", "official_success": False},
        Candidate("ask_help"), {"executed": True}, None, loop_exhausted=False,
    )
    assert category == "no_legal_candidate"
    assert "no oracle binding evidence" in detail
