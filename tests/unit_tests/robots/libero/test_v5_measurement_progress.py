"""Measured anti-loop state, conditional release and finite VLA macros."""

from dataclasses import replace
import random

import pytest

from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_state import Candidate, Entity, candidates, measurement_progress_blocked, recent_failures, serialize


def entity(eid="e1", name="bowl", x=0.):
    return Entity(eid, name, (x, 0., 1.), (x-.03, -.03, .97), (x+.03, .03, 1.03))


@pytest.mark.parametrize("opening,held,legal", [(None, None, False), (.08, None, False),
                                              (.075, None, False), (.074, None, True),
                                              (.08, "e1", True)])
def test_release_requires_closed_gripper_or_measured_held_object(opening, held, legal):
    choices = candidates([entity()], "move bowl", (0., 0., 1.2), held, [], random.Random(1),
                         gripper_opening=opening)
    assert (Candidate("release") in choices) is legal


def test_repeated_measured_failure_stays_blocked_until_cumulative_scene_change():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for receipt in ({"effect": "no_effect"}, {"verification": "failed", "grasp_verified": False}):
        recovery.observe(action, state, state, receipt)
    assert action.text() in recovery.status()["blocked_actions"]
    for _ in range(10):
        recovery.observe(Candidate("ask_help"), state, state, {"effect": "no_effect"})
    choices = candidates([obj], "move bowl", (0., 0., 1.2), None, [], random.Random(1),
                         recovery_status=recovery.status(), gripper_opening=.08)
    assert action not in choices
    assert measurement_progress_blocked(action, recovery.status())
    assert not measurement_progress_blocked(Candidate("grasp", obj.id, mode="yaw_90"), recovery.status())
    assert Candidate("grasp", obj.id, mode="above_10cm") in choices
    text = serialize("move bowl", [obj], .08, None, [], choices=choices, failure_counts=True,
                     recovery_status=recovery.status())
    assert f"blocked {action.text()} failures=2:verification_failed until=measured_change" in text
    after = MeasuredRecovery.snapshot([replace(obj, xyz=(.02, 0., 1.))], None, .08)
    recovery.observe(Candidate("reperceive"), state, after, {"effect": "measured_change"})
    assert recovery.status()["blocked_actions"] == []
    assert recovery.status()["action_failures"] == {}
    assert action in candidates([obj], "move bowl", (0., 0., 1.2), None, [], random.Random(1),
                                recovery_status=recovery.status())


def test_metadata_noise_and_claimed_receipt_progress_cannot_release_a_block():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("reperceive")
    for _ in range(2):
        recovery.observe(action, state, state, {"effect": "no_effect"})
    after = MeasuredRecovery.snapshot([replace(obj, source_step=100, xyz=(.003, 0., 1.))], None, .079)
    recovery.observe(Candidate("retreat"), state, after, {"effect": "measured_change", "count": 999})
    assert action.text() in recovery.status()["blocked_actions"]
    assert recovery.reperceive_cooldown == 0
    choices = candidates([obj], "move bowl", (0., 0., 1.2), None, [], random.Random(1),
                         recovery_status=recovery.status())
    assert action not in choices
    assert Candidate("wrist_scan") in choices


def test_execution_error_with_no_effect_counts_toward_measurement_block():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for receipt in ({"effect": "unmeasured", "verification": "unverified"},
                    {"effect": "no_effect", "verification": "execution_error"}):
        for _ in range(2):
            recovery.observe(action, state, state, receipt)
    assert recovery.status()["blocked_actions"] == [action.text()]
    assert recovery.status()["action_failures"][action.text()] == {
        "count": 2, "kind": "execution_error"
    }


def test_measurement_changes_in_held_robot_state_reset_block():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for _ in range(2):
        recovery.observe(action, state, state, {"grasp_verified": False})
    after = MeasuredRecovery.snapshot([obj], obj.id, .03)
    recovery.observe(Candidate("grasp", obj.id, mode="above_10cm"), state, after,
                     {"grasp_verified": True})
    assert recovery.status()["blocked_actions"] == []


def test_empty_gripper_opening_and_pure_eef_motion_do_not_clear_a_grasp_block():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for _ in range(2):
        recovery.observe(action, state, state, {"grasp_verified": False})
    after = {**MeasuredRecovery.snapshot([obj], None, .001), "eef_xyz": [.5, .5, 1.5]}
    recovery.observe(Candidate("release"), state, after, {"effect": "measured_change"})
    assert action.text() in recovery.status()["blocked_actions"]


def test_small_scene_moves_accumulate_to_the_measured_change_threshold():
    obj = entity()
    state = MeasuredRecovery.snapshot([obj], None, .08)
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", obj.id, mode="direct")
    for _ in range(2):
        recovery.observe(action, state, state, {"grasp_verified": False})
    previous = state
    for x in (.005, .01, .015):
        after = MeasuredRecovery.snapshot([replace(obj, xyz=(x, 0., 1.))], None, .08)
        recovery.observe(Candidate("retreat"), previous, after, {"effect": "measured_change"})
        assert action.text() in recovery.status()["blocked_actions"]
        previous = after
    after = MeasuredRecovery.snapshot([replace(obj, xyz=(.021, 0., 1.))], None, .08)
    recovery.observe(Candidate("retreat"), previous, after, {"effect": "measured_change"})
    assert recovery.status()["blocked_actions"] == []


def test_no_effect_is_visible_and_unknown_is_not_counted_as_a_failed_candidate():
    action = Candidate("release")
    receipts = [{"tool": "release", "effect": "no_effect"},
                {"tool": "release", "effect": "unmeasured"}]
    assert recent_failures(action, receipts) == (1, "no_effect")


@pytest.mark.parametrize("text", ["vla_subtask(e1,e2,on)", "vla_subtask(e1,e2,in)",
                                 "vla_subtask(e3,open)", "vla_subtask(e3,close)",
                                 "vla_subtask(e3,turn_on)", "vla_subtask(e3,turn_off)"])
def test_vla_subtask_candidates_round_trip(text):
    assert Candidate.from_text(text).text() == text


@pytest.mark.parametrize("text", ["vla_subtask(e1,grasp)", "vla_subtask(e1,e2,open)",
                                 "vla_subtask(pick up bowl)", "vla_subtask()"])
def test_vla_subtask_rejects_free_prompts_or_wrong_arity(text):
    with pytest.raises(ValueError, match="unsupported candidate"):
        Candidate.from_text(text)


def test_macros_keep_bound_source_and_split_skills_within_the_24_choice_cap():
    objects = [entity(f"e{i}", "bowl", i/10) for i in range(10)]
    targets = [entity(f"e{i}", "plate", i/10) for i in range(10, 16)]
    macros = [Candidate("vla_subtask", f"e{i}", f"e{i+6}", "on") for i in range(4, 10)]
    choices = candidates(objects+targets, "put the bowl on the plate", (0., 0., 1.2), None,
                         [], random.Random(1), vla_subtasks=macros, card={"step": 1},
                         gripper_opening=.08)
    assert len(choices) <= 24 and len(set(choices)) == len(choices)
    for macro in macros:
        assert macro in choices
        assert Candidate("grasp", macro.object, mode="direct") in choices
        assert Candidate.from_text(macro.text()) == macro
    assert Candidate("card_next") in choices


def test_held_object_macro_and_fixture_macro_keep_matching_split_choices():
    obj, target, fixture = entity(), entity("e2", "plate"), entity("e3", "microwave")
    macros = [Candidate("vla_subtask", obj.id, target.id, "on"),
              Candidate("vla_subtask", fixture.id, mode="open")]
    choices = candidates([obj, target, fixture], "put bowl on plate and open microwave", (0.,0.,1.2),
                         obj.id, [], random.Random(1), vla_subtasks=macros)
    assert all(c in choices for c in macros)
    assert Candidate("place", obj.id, target.id, "on") in choices
    assert Candidate("articulate", fixture.id, mode="open") in choices
