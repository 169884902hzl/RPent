"""Physical completion does not replace the required explicit finish choice."""

from harness_v5_eval import _termination_category


def test_known_no_legal_candidate_preserves_program_termination():
    result = {"status": "error", "error": "NoLegalCandidate: no supported candidate",
              "termination_category": "no_legal_candidate"}
    assert _termination_category(result, None, None, None, loop_exhausted=False) == (
        "no_legal_candidate", "NoLegalCandidate: no supported candidate")
from robots.libero.v5_state import Candidate


def test_upstream_choice_failure_after_grasp_is_not_a_skill_or_model_outcome():
    result = {"status": "error", "decisions": 1,
              "error_stage": "decision_service",
              "error": 'RuntimeError: choice service HTTP 422: {"error": "HTTP 520"}'}
    category, detail = _termination_category(
        result, Candidate("grasp", "e5", mode="above_10cm"),
        {"grasp_verified": True}, None, loop_exhausted=False,
        accounting_v2=True,
    )
    assert category == "model_error"
    assert detail == result["error"]


def test_service_error_preserves_prior_native_success_as_a_separate_fact():
    category, _ = _termination_category(
        {"status": "error", "official_success": True, "native_terminated": True,
         "error_stage": "decision_service", "error": "HTTP 520"},
        None, None, None, loop_exhausted=False, accounting_v2=True,
    )
    assert category == "success"


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


def test_persistence_budget_end_after_rejected_finish_is_not_false_completion():
    result = {"status": "completed", "official_success": False, "persist_attempts_v1": True}
    category, _ = _termination_category(result, Candidate("finish"),
        {"executed": False, "verification": "environment_incomplete"}, None,
        loop_exhausted=True, accounting_v2=True)
    assert category == "budget_exhausted"


def test_persistence_keeps_recovery_after_help_and_removes_twice_rejected_finish():
    import random
    from robots.libero.v5_state import Entity, candidates
    obj = Entity("e1", "bowl", (0,0,1), (-.03,-.03,.95), (.03,.03,1.05))
    receipts = [{"tool":"grasp", "object":"e1", "grasp_verified":False},
                {"tool":"ask_help", "executed":False}]
    choices = candidates([obj], "pick up the bowl", (0,0,1.2), None, receipts,
                         random.Random(1), persist_attempts=True, finish_rejections=2)
    assert Candidate("regrasp_restage", "e1") in choices
    assert Candidate("reperceive") in choices
    assert Candidate("finish") not in choices
    assert len(choices) <= 24


def test_rejected_terminal_request_does_not_move_or_claim_execution():
    from types import SimpleNamespace
    from robots.libero.v5_runtime import V5Executor
    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), SimpleNamespace())
    for tool in ("ask_help", "finish"):
        receipt = executor.reject_terminal_action(Candidate(tool))
        assert not receipt["executed"]
        assert receipt["message"]
        assert executor.receipts[-1] is receipt


def test_card_finish_is_rejected_and_card_does_not_advance_before_native_success():
    from types import SimpleNamespace
    from harness_v5_eval import _execute_action
    from robots.libero.v5_cards import advance_card
    from robots.libero.v5_runtime import V5Executor

    executor = V5Executor(SimpleNamespace(primitives=SimpleNamespace()), SimpleNamespace(entities={}))
    executor.p.env = SimpleNamespace(terminated=False)
    result = {"persist_attempts_v1": True, "rejected_finish_attempts": 0, "ask_help_attempts": 0}
    selected, resolved = Candidate("card_next"), Candidate("finish")
    view = {"selector": {"skill": "finish"}}
    for count in (1, 2):
        receipt, effective = _execute_action(executor, selected, view, resolved, result)
        assert effective == resolved
        assert result["rejected_finish_attempts"] == count
        assert receipt["tool"] == "finish" and receipt["requested_tool"] == "card_next"
        assert not receipt["executed"]
        assert not advance_card(view, selected, receipt, resolved)

    executor.p.env.terminated = True
    receipt, _ = _execute_action(executor, selected, view, resolved, result)
    assert receipt["executed"]
    assert advance_card(view, selected, receipt, resolved)
    assert result["rejected_finish_attempts"] == 2
