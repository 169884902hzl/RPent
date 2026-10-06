"""Recovery uses measured changes and suppresses repeated perception no-ops."""

from dataclasses import replace
import random
import pytest

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


def test_scene_changes_do_not_allow_a_sixth_identical_skill_attempt():
    """Saved failures moved the object yet never completed the transfer."""
    obj, state = measured()
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for count in range(5):
        after = MeasuredRecovery.snapshot([
            replace(obj, xyz=(.03 * (count + 1), 0., 1.))], None, .08)
        recovery.observe(action, state, after, {"verification": "failed", "effect": "measured_change"})
        recovery.observe(Candidate("clear_view"), after, state, {"effect": "measured_change"})
    choices = candidates([obj], "pick the bowl", (0., 0., 1.2), None, [], random.Random(2),
                         recovery_status=recovery.status())
    assert action not in choices
    assert Candidate("grasp", obj.id, mode="above_10cm") in choices
    assert Candidate("grasp", obj.id, mode="yaw_90") in choices
    assert Candidate("vla_subtask", obj.id, mode="open").text() not in recovery.status()["attempt_limit_actions"]


def test_attempt_bookkeeping_does_not_add_state_rows_or_claim_verification_failures():
    obj, state = measured()
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for _ in range(5):
        recovery.observe(action, state, state, {"verification": "verified", "effect": "measured_change"})
    status = recovery.status()
    assert action.text() in status["attempt_limit_actions"]
    assert not status["action_failures"] and not status["blocked_actions"]
    args = ("pick bowl", [obj], .08, None, [])
    assert serialize(*args, recovery_status=status) == serialize(
        *args, recovery_status={k: v for k, v in status.items() if k != "attempt_limit_actions"})


@pytest.mark.parametrize("after_step,red,unblocks", [(3, .08, True), (2, .08, False), (3, 0., False)])
def test_only_new_measured_coil_changes_release_action_blocks(after_step, red, unblocks):
    obj, state = measured()
    action = Candidate("articulate", obj.id, mode="turn_on")
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    for _ in range(2):
        recovery.observe(action, state, state, {"effect": "no_effect"})
    assert action.text() in recovery.blocked_actions
    receipt = {"articulation_state": {"before": {"src": "perception", "entity": obj.id,
                "visible": True, "source_step": 2, "features": {"red_fraction": 0.}},
                "after": {"src": "perception", "entity": obj.id, "visible": True,
                "source_step": after_step, "features": {"red_fraction": red}}}}
    recovery.observe(Candidate("vla_subtask", obj.id, mode="turn_on"), state, state, receipt)
    assert (action.text() not in recovery.blocked_actions) is unblocks


@pytest.mark.parametrize("interleaved", ["ask_help", "retreat", "finish", "clear_view"])
def test_noop_interleaved_actions_do_not_reset_unchanged_perception_count(interleaved):
    obj, state = measured()
    recovery = MeasuredRecovery()
    recovery.observe(Candidate("reperceive"), state, state)
    recovery.observe(Candidate(interleaved), state, state)
    recovery.observe(Candidate("reperceive"), state, state)
    assert recovery.status() == {"no_progress_steps": 3, "reperceive_cooldown": 3}
    choices = candidates([obj], "pick bowl", (0., 0., 1.2), None, [], random.Random(3),
                         recovery_status=recovery.status())
    assert Candidate("reperceive") not in choices


def test_real_progress_between_reperceptions_resets_the_cooldown_trigger():
    obj, state = measured()
    held = MeasuredRecovery.snapshot([obj], obj.id, .03)
    recovery = MeasuredRecovery()
    recovery.observe(Candidate("reperceive"), state, state)
    recovery.observe(Candidate("grasp", obj.id, mode="direct"), state, held)
    recovery.observe(Candidate("reperceive"), held, held)
    assert recovery.status() == {"no_progress_steps": 1, "reperceive_cooldown": 0}


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


def test_saved_trace_rerender_matches_live_recovery_before_and_after_the_action():
    from dataclasses import asdict
    from scripts.rerender_v5_format118_20261002 import measured_recovery_at

    obj, _ = measured()
    context = serialize("pick the bowl", [obj], .08, None, [])
    trace = [{"selected": tool+'()', "receipt": {"tool": tool},
              "measurements": [asdict(obj)], "post_measurements": [asdict(obj)],
              "request": {"context": context}, "post_request": {"context": context}}
             for tool in ("reperceive", "reperceive", "ask_help")]
    assert measured_recovery_at(trace, 0) == {"no_progress_steps": 0, "reperceive_cooldown": 0}
    assert measured_recovery_at(trace, 2) == {"no_progress_steps": 2, "reperceive_cooldown": 3}
    assert measured_recovery_at(trace, 2, True) == {"no_progress_steps": 3, "reperceive_cooldown": 2}
    trace[2]["post_request"]["context"] = serialize("pick the bowl", [obj], .03, obj.id, [])
    assert measured_recovery_at(trace, 2, True)["no_progress_steps"] == 0


def test_saved_trace_cannot_invent_recovery_when_post_measurements_are_missing():
    from scripts.rerender_v5_format118_20261002 import measured_recovery_at

    with pytest.raises(ValueError, match="recorded_recovery_transition_missing"):
        measured_recovery_at([{"measurements": [], "request": {"context": "robot gripper_opening=0.08 held=none"}}], 1)


def test_execution_error_blocks_only_the_matching_grasp_for_three_decisions():
    obj, _ = measured()
    failed = {"tool": "grasp", "object": obj.id, "mode": "direct",
              "verification": "execution_error"}
    receipts = [failed]
    for _ in range(3):
        choices = candidates([obj], "pick bowl", (0., 0., 1.2), None,
                             receipts, random.Random(3), execution_error_cooldown=True)
        assert Candidate("grasp", obj.id, mode="direct") not in choices
        assert Candidate("grasp", obj.id, mode="above_10cm") in choices
        assert Candidate("grasp", obj.id, mode="yaw_90") in choices
        receipts.append({"tool": "retreat", "executed": True})
    choices = candidates([obj], "pick bowl", (0., 0., 1.2), None,
                         receipts, random.Random(3), execution_error_cooldown=True)
    action = Candidate("grasp", obj.id, mode="direct")
    assert action in choices
    assert f"candidate {action.text()} failures=1:execution_error" in serialize(
        "pick bowl", [obj], .08, None, receipts, choices=choices, failure_counts=True)


@pytest.mark.parametrize("reason", ["approach_not_reached", "wrist_pose_not_reached", "waypoint_not_reached"])
def test_recoverable_measured_motion_failure_is_not_an_execution_error_cooldown(reason):
    obj, _ = measured()
    action = Candidate("grasp", obj.id, mode="direct")
    failed = {"tool": "grasp", "object": obj.id, "mode": "direct",
              "verification": "failed", "failure_reason": reason}
    choices = candidates([obj], "pick bowl", (0., 0., 1.2), None,
                         [failed], random.Random(3), execution_error_cooldown=True)
    assert action in choices
    assert f"candidate {action.text()} failures=1:{reason}" in serialize(
        "pick bowl", [obj], .08, None, [failed], choices=choices, failure_counts=True)


def test_execution_error_cooldown_keeps_physical_failures_and_legacy_choices():
    obj, _ = measured()
    action = Candidate("grasp", obj.id, mode="direct")
    for kind, flag in (("failed", True), ("execution_error", False)):
        choices = candidates([obj], "pick bowl", (0., 0., 1.2), None,
                             [{"tool": "grasp", "object": obj.id, "mode": "direct",
                               "verification": kind}], random.Random(3),
                             execution_error_cooldown=flag)
        assert action in choices


def test_execution_error_cooldown_covers_card_resolved_action_and_target_identity():
    from robots.libero.v5_state import execution_error_blocked
    receipt = {"verification": "execution_error", "card_action": "place(e7,e8,on)"}
    assert execution_error_blocked(Candidate("place", "e7", "e8", "on"), [receipt])
    assert not execution_error_blocked(Candidate("place", "e7", "e9", "on"), [receipt])
    receipt.update(verification="failed", failure_reason="waypoint_not_reached")
    assert not execution_error_blocked(Candidate("place", "e7", "e8", "on"), [receipt])
    assert not execution_error_blocked(Candidate("place", "e7", "e9", "on"), [receipt])


def test_unrelated_clear_view_geometry_does_not_release_failed_grasp():
    bowl, _ = measured()
    cabinet = replace(bowl, id="e8", name="cabinet top surface", part_of="e9")
    before = MeasuredRecovery.snapshot([bowl, cabinet], None, .08)
    action = Candidate("grasp", bowl.id, mode="direct")
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    for _ in range(2):
        recovery.observe(action, before, before, {"verification": "failed"})
    changed = MeasuredRecovery.snapshot([bowl, replace(cabinet, upper=(.03, .03, 1.416))], None, .08)
    recovery.observe(Candidate("clear_view"), before, changed, {"effect": "no_effect"})
    assert action.text() in recovery.blocked_actions
    assert recovery.action_failures[action.text()]["count"] == 2
    choices = candidates([bowl, cabinet], "pick bowl", (0, 0, 1.2), None, [], random.Random(3),
                         recovery_status=recovery.status())
    assert action not in choices


def test_related_object_motion_after_another_action_releases_failed_grasp():
    bowl, before = measured()
    action = Candidate("grasp", bowl.id, mode="direct")
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    for _ in range(2):
        recovery.observe(action, before, before, {"verification": "failed"})
    moved = MeasuredRecovery.snapshot([replace(bowl, xyz=(.03, 0, 1.))], None, .08)
    recovery.observe(Candidate("regrasp_restage", bowl.id), before, moved, {"effect": "measured_change"})
    assert action.text() not in recovery.blocked_actions
    assert action.text() not in recovery.action_failures


def test_failed_attempt_own_motion_cannot_release_itself_on_next_reperception():
    bowl, first = measured()
    action = Candidate("grasp", bowl.id, mode="direct")
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    second = MeasuredRecovery.snapshot([replace(bowl, xyz=(.04, 0, 1.))], None, .08)
    third = MeasuredRecovery.snapshot([replace(bowl, xyz=(.08, 0, 1.))], None, .08)
    recovery.observe(action, first, second, {"verification": "failed", "effect": "measured_change"})
    recovery.observe(action, second, third, {"verification": "failed", "effect": "measured_change"})
    recovery.observe(Candidate("reperceive"), third, third, {"effect": "no_effect"})
    assert action.text() in recovery.blocked_actions
    assert recovery.action_failures[action.text()]["count"] == 2


def test_measured_fixture_part_motion_releases_parent_articulation():
    cabinet, _ = measured()
    cabinet = replace(cabinet, name="cabinet")
    drawer = replace(cabinet, id="e8", name="cabinet top drawer", part_of=cabinet.id)
    first = MeasuredRecovery.snapshot([cabinet, drawer], None, .08)
    action = Candidate("articulate", cabinet.id, mode="open")
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    for _ in range(2):
        recovery.observe(action, first, first, {"verification": "failed"})
    opened = MeasuredRecovery.snapshot([cabinet, replace(drawer, xyz=(0, .03, 1.))], None, .08)
    recovery.observe(Candidate("articulate", drawer.id, mode="open"), first, opened,
                     {"verification": "verified", "effect": "measured_change"})
    assert action.text() not in recovery.blocked_actions
