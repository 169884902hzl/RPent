"""Recovery uses measured changes and suppresses repeated perception no-ops."""

from dataclasses import replace
import random

from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_state import Candidate, Entity, candidates, serialize


def measured():
    obj = Entity("e7", "bowl", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    return obj, MeasuredRecovery.snapshot([obj], None, .08)


def test_two_unchanged_reperceptions_are_removed_for_exactly_three_decisions():
    obj, state = measured()
    recovery = MeasuredRecovery()
    for _ in range(2):
        recovery.observe(Candidate("reperceive"), state, state)
    assert recovery.status() == {"no_progress_steps": 2, "reperceive_cooldown": 3}
    for _ in range(3):
        choices = candidates([obj], "pick the bowl", (0., 0., 1.2), None, [], random.Random(2),
                             recovery_status=recovery.status())
        assert Candidate("reperceive") not in choices
        assert Candidate("wrist_scan") in choices and Candidate("clear_view") in choices
        recovery.observe(Candidate("ask_help"), state, state)
    choices = candidates([obj], "pick the bowl", (0., 0., 1.2), None, [], random.Random(2),
                         recovery_status=recovery.status())
    assert Candidate("reperceive") in choices
    assert recovery.ineffective_actions == 5


def test_camera_steps_and_small_measurement_jitter_are_not_task_progress():
    obj, state = measured()
    recovery = MeasuredRecovery()
    after = MeasuredRecovery.snapshot([replace(obj, xyz=(.003, 0., 1.), source_step=100)], None, .079)
    recovery.observe(Candidate("reperceive"), state, after)
    assert recovery.no_progress_steps == 1
    held = MeasuredRecovery.snapshot([obj], obj.id, .03)
    recovery.observe(Candidate("grasp", obj.id, mode="direct"), after, held)
    assert recovery.no_progress_steps == 0
    moved = MeasuredRecovery.snapshot([replace(obj, xyz=(.1, 0., 1.))], obj.id, .03)
    assert not recovery.unchanged(held, moved)


def test_rejected_help_exposes_concrete_recovery_without_exceeding_candidate_cap():
    obj, _ = measured()
    receipt = {"tool": "ask_help", "executed": False, "verification": "help_unavailable"}
    choices = candidates([obj], "pick bowl", (0., 0., 1.2), None, [receipt], random.Random(3),
                         recovery_status={"no_progress_steps": 1, "reperceive_cooldown": 0})
    assert Candidate("regrasp_restage", obj.id) in choices
    assert Candidate("wrist_scan") in choices and Candidate("clear_view") in choices
    assert len(choices) <= 24 and len(set(choices)) == len(choices)
    for choice in choices:
        assert Candidate.from_text(choice.text()) == choice


def test_recovery_extension_is_absent_from_legacy_state_and_identical_for_collection():
    obj, _ = measured()
    status = {"no_progress_steps": 4, "reperceive_cooldown": 2}
    assert "recovery " not in serialize("pick bowl", [obj], .08, None, [])
    context = serialize("pick bowl", [obj], .08, None, [], recovery_status=status)
    assert "recovery no_progress_steps=4 reperceive_cooldown=2" in context
    assert "sim_truth" not in context and "predicate" not in context
