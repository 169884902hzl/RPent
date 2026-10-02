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


def test_v2_native_success_keeps_explicit_finish_as_a_separate_metric():
    result = {"status": "completed", "official_success": True,
              "native_terminated": True, "correct_finish": False}
    category, _ = _termination_category(result, Candidate("ask_help"), {}, None,
                                       loop_exhausted=False, accounting_v2=True)
    assert category == "success"
    assert result["correct_finish"] is False


def test_v2_grasp_abandonment_is_not_missing_perception():
    receipts = [{"tool": "grasp", "grasp_verified": False, "verification": "failed"},
                {"tool": "reperceive"}, {"tool": "ask_help"}]
    category, _ = _termination_category({"status": "completed"}, Candidate("ask_help"),
                                       receipts[-1], None, loop_exhausted=False,
                                       accounting_v2=True, receipts=receipts)
    assert category == "grasp_failure_abandonment"


def test_v2_execution_error_survives_a_following_control_receipt():
    receipts = [{"tool": "place", "verification": "execution_error", "error": "waypoint"},
                {"tool": "reperceive"}, {"tool": "ask_help"}]
    category, detail = _termination_category({"status": "completed"}, Candidate("ask_help"),
                                           receipts[-1], None, loop_exhausted=False,
                                           accounting_v2=True, receipts=receipts)
    assert (category, detail) == ("skill_execution_error", "waypoint")


def test_v2_native_success_retains_a_late_error_without_misclassifying_completion():
    result = {"status":"error", "error":"post-measurement failed", "official_success":True,
              "native_terminated":True, "correct_finish":False}
    category, _ = _termination_category(result, Candidate("place","e1","e2","on"),
                                       {}, None, loop_exhausted=False, accounting_v2=True)
    assert category == "success"
    assert result["error"] == "post-measurement failed"
    assert result["correct_finish"] is False


def test_v2_original_oracle_missing_binding_keeps_perception_evidence():
    category, _ = _termination_category({"status":"completed"}, Candidate("ask_help"), {},
                                       {"source_entity":None}, loop_exhausted=False,
                                       accounting_v2=True)
    assert category == "perception_missing_object"


def test_current_token_error_is_not_reclassified_as_an_earlier_skill_failure():
    from robots.libero.v5_termination import classify_v2

    result = {"status": "error", "official_success": False,
              "termination_category": "over_token", "error": "Longest prompt has 3145 tokens; limit is 3072."}
    previous = [{"tool": "place", "verification": "execution_error", "error": "waypoint"}]
    assert classify_v2(result, Candidate("place", "e1", "e2", "in"), previous) is None
    assert result["termination_category"] == "over_token"
