"""Failed contact motion must not reset its own repeated-failure history."""

from dataclasses import replace

import pytest

from robots.libero.v5_recovery import MeasuredRecovery
from robots.libero.v5_state import Candidate, Entity


@pytest.mark.parametrize("verification", ["failed", "execution_error"])
def test_moving_failed_subtask_is_blocked_after_second_attempt(verification):
    obj = Entity("e7", "butter", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("vla_subtask", "e7", "e8", "in")
    for index in range(2):
        moved = replace(obj, xyz=(obj.xyz[0] + .03, 0., 1.),
                        lower=(obj.lower[0] + .03, -.03, .95),
                        upper=(obj.upper[0] + .03, .03, 1.05))
        before = recovery.snapshot([obj], None, .08)
        after = recovery.snapshot([moved], None, .08)
        recovery.observe(action, before, after,
                         {"verification": verification, "place_verified": False,
                          "effect": "measured_change"})
        assert recovery.action_failures[action.text()]["count"] == index + 1
        obj = moved
    assert action.text() in recovery.blocked_actions
    # A different recovery action with measured scene progress releases it.
    after = recovery.snapshot([replace(obj, xyz=(.3, 0., 1.))], None, .08)
    recovery.observe(Candidate("reperceive"), recovery.snapshot([obj], None, .08), after,
                     {"effect": "measured_change"})
    assert action.text() not in recovery.blocked_actions


def test_verified_scene_progress_clears_same_action_failure():
    obj = Entity("e7", "bowl", (0., 0., 1.), (-.03, -.03, .95), (.03, .03, 1.05))
    recovery = MeasuredRecovery(measurement_progress_blocking=True)
    action = Candidate("grasp", "e7", mode="direct")
    state = recovery.snapshot([obj], None, .08)
    recovery.observe(action, state, state, {"grasp_verified": False})
    after = recovery.snapshot([replace(obj, xyz=(0., 0., 1.1))], "e7", .04)
    recovery.observe(action, state, after, {"grasp_verified": True, "verification": "verified"})
    assert action.text() not in recovery.action_failures
