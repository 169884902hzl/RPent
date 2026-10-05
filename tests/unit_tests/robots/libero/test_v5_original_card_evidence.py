"""Physical evidence gates for original-only category-card reconstruction."""

from robots.libero.v5_original_card_evidence import reconstruct_card


def _record(decision, selected, *, measurements=None, official=False):
    measurements = measurements or [
        {"id": "e1", "name": "alphabet soup", "src": "perception"},
        {"id": "e2", "name": "basket", "src": "perception"},
    ]
    return {
        "decision": decision,
        "selected": selected,
        "official_success": official,
        "receipt": {"tool": selected.split("(")[0], "executed": True,
                    "verification": "verified"},
        "request": {"context": "instruction\nstate", "instruction": "choose", "options": [selected]},
        "candidates": [selected], "measurements": measurements,
    }


def _label(decision, action, before, after, receipt=None, accepted=True):
    return {
        "step": decision,
        "request": {"state": "instruction\nstate", "questions": {"action": {"criteria": {"C0": action}}}},
        "label_evidence": {"physical_branch_checked": True, "branches": [{
            "action": action, "accepted": accepted,
            "receipt": receipt or {"tool": action.split("(")[0], "executed": True,
                                    "verification": "failed", "place_verified": False},
            "before": before, "after": after,
        }]},
    }


def _card():
    return {"version": "category-card/1", "origin": "original_oracle",
            "steps": [{"skill": "grasp", "object_category": "alphabet soup", "mode": "direct"},
                       {"skill": "finish"}],
            "source_episode": {"suite": "libero_10", "task": 0, "seed": 15},
            "source_choices_sha256": "trace-sha"}


def test_rebuild_requires_predicate_gain_for_place():
    before = {"goals": [["in", "alphabet_soup_1", "basket_1_contain_region"]],
              "satisfied": [False], "done": False}
    after = {**before, "satisfied": [True], "done": True}
    grasp = _record(0, "grasp(e1,direct)")
    place = _record(1, "place(e1,e2,in)", official=True)
    labels = {1: _label(1, "place(e1,e2,in)", before, after)}
    rebuilt, audit = reconstruct_card(_card(), [grasp, place], labels)
    assert rebuilt is not None
    assert rebuilt["steps"] == [
        {"skill": "grasp", "object_category": "alphabet soup", "mode": "direct"},
        {"skill": "place", "object_category": "alphabet soup", "target_category": "basket", "mode": "in"},
        {"skill": "finish"},
    ]
    assert audit["status"] == "physically_evidenced_plan"


def test_rebuild_does_not_infer_place_from_final_success():
    before = {"goals": [["in", "alphabet_soup_1", "basket_1_contain_region"]],
              "satisfied": [False], "done": False}
    after = {**before, "satisfied": [False], "done": False}
    grasp = _record(0, "grasp(e1,direct)")
    finish = _record(1, "finish()", official=True)
    # A finish-only successful trace has no accepted physical action.
    rebuilt, audit = reconstruct_card(_card(), [grasp, finish], {})
    assert rebuilt is None
    assert audit["reason"] == "not_every_goal_has_positive_selected_action_evidence"


def test_rebuild_rejects_failed_action_even_when_episode_finally_succeeds():
    before = {"goals": [["in", "alphabet_soup_1", "basket_1_contain_region"]],
              "satisfied": [False], "done": False}
    after = {**before, "satisfied": [False], "done": False}
    failed_place = _record(1, "place(e1,e2,in)", official=True)
    failed_label = _label(1, "place(e1,e2,in)", before, after, accepted=False)
    rebuilt, audit = reconstruct_card(_card(), [failed_place], {1: failed_label})
    assert rebuilt is None
    assert any(item["reason"] == "physical_branch_not_accepted_without_error" for item in audit["decisions"])
