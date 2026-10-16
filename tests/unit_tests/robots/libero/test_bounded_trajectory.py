"""Offline checks for continuous waypoint motion and delayed decisions."""
from concurrent.futures import Future

import numpy as np
import pytest

from rpent.skill_package.contract import DecisionLookahead, FailureMemory
from rpent.skill_package.trajectory import Limits, brake, plan


def test_blended_waypoints_are_c2_and_do_not_stop():
    path = plan([[0, 0, 0], [.1, .05, .02], [.2, .05, .03]])
    for first, second in zip(path.segments[:-1], path.segments[1:]):
        for derivative in range(4):
            np.testing.assert_allclose(first.at(first.duration, derivative), second.at(0, derivative), atol=1e-8)
    assert np.linalg.norm(path.at(path.waypoint_times[0], 1)) > .01
    unblended = plan([[0, 0, 0], [.1, .05, .02], [.2, .05, .03]], blend=False)
    assert np.linalg.norm(unblended.at(unblended.waypoint_times[0], 1)) < 1e-10
    for derivative in (1, 2, 3):
        np.testing.assert_allclose(path.at(0, derivative), 0, atol=1e-8)
        np.testing.assert_allclose(path.at(path.duration, derivative), 0, atol=1e-8)


def test_vector_limits_and_no_axis_clip():
    limit = Limits(.15, .5, 2.)
    path = plan([[0, 0, 0], [.2, .2, .2], [.3, -.1, .1]])
    for segment in path.segments:
        for derivative, bound in enumerate((limit.velocity, limit.acceleration, limit.jerk), 1):
            assert segment.maximum(derivative, slice(None)) <= bound*1.00001
    np.testing.assert_allclose(path.at(0), [0, 0, 0])
    np.testing.assert_allclose(path.at(path.duration), [.3, -.1, .1], atol=1e-10)


def test_reversal_stops_and_brake_preserves_initial_derivatives():
    path = plan([[0, 0, 0], [.1, 0, 0], [0, 0, 0]])
    np.testing.assert_allclose(path.at(path.waypoint_times[0], 1), 0, atol=1e-10)
    tail = brake([.2, .1, .3], [.07, .02, 0], [.01, 0, 0])
    for derivative, expected in enumerate(([.2, .1, .3], [.07, .02, 0], [.01, 0, 0])):
        np.testing.assert_allclose(tail.at(0, derivative), expected, atol=1e-10)
    for derivative in (1, 2):
        np.testing.assert_allclose(tail.at(tail.duration, derivative), 0, atol=1e-10)
    assert max(s.maximum(3, slice(None)) for s in tail.segments) <= 2.00001


def test_vla_handoff_preserves_inherited_jerk_then_brakes():
    v = [-.03606148785, -.06039458255, -.06518512859]
    a = [-.1031564573, -.0154140281, -.2916821032]
    j = [-3.403462599, .917115658, -5.55505509]
    path = brake([0, 0, 0], v, a, jerk=j)
    for derivative, expected in enumerate(([0, 0, 0], v, a, j)):
        np.testing.assert_allclose(path.at(0, derivative), expected, atol=1e-9)
    for left, right in zip(path.segments[:-1], path.segments[1:]):
        for derivative in range(4):
            np.testing.assert_allclose(left.at(left.duration, derivative), right.at(0, derivative), atol=1e-8)
    for derivative in (1, 2, 3):
        np.testing.assert_allclose(path.at(path.duration, derivative), 0, atol=1e-8)


def test_delayed_decision_does_not_block_current_chunk():
    future = Future()
    seen = []
    def submit(request):
        seen.append(request)
        return future
    lookahead = DecisionLookahead(submit, .3)
    lookahead.poll(.4, lambda: {"observation_id": "x", "revision": 0})
    assert seen == []
    lookahead.poll(.2, lambda: {"observation_id": "x", "revision": 0})
    assert len(seen) == 1
    assert lookahead.take("x", 0) is None
    future.set_result({})
    assert lookahead.take("changed", 1) is None


def test_no_effect_blocks_until_measured_change():
    c = {"id": "a", "skill": "release", "parameters": {}}
    memory = FailureMemory()
    for _ in range(2):
        memory.record(c, "no_effect", "no_measured_change")
    assert memory.apply([c]) == []
    memory.tick(scene_changed=False)
    assert memory.apply([c]) == []
    memory.tick(scene_changed=True)
    assert memory.apply([c])[0]["recent_failures"] == 0


@pytest.mark.parametrize("waypoints", ([[0, 0, 0]], [[0, 0, float('nan')], [0, 1, 2]]))
def test_bad_path_is_rejected(waypoints):
    with pytest.raises(ValueError):
        plan(waypoints)
