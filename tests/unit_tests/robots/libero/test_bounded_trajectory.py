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


@pytest.mark.parametrize("stationary_group", (slice(0, 3), slice(3, 6)))
def test_mixed_pose_blending_does_not_move_a_stationary_group(stationary_group):
    # Drawer entry is followed by rotation at fixed XYZ. Previously the 6D
    # bisector carried descent velocity into that rotation and dipped 3cm.
    points = np.array([[0., .02, 1.16, 0., 0., 0.],
                       [.0272, -.0127, 1.0216, 0., 0., 0.],
                       [.0272, -.0127, 1.0216, 0., 0., 1.57]])
    if stationary_group.start == 3:
        points = np.concatenate([points[:, 3:], points[:, :3]], axis=1)
    groups = ((slice(0, 3), Limits()), (slice(3, 6), Limits(.7, 1.5, 6.)))
    path = plan(points, groups=groups)
    for t in np.linspace(path.waypoint_times[0], path.duration, 201):
        np.testing.assert_allclose(path.at(t)[stationary_group], points[-1, stationary_group], atol=1e-10)
        for order in (1, 2, 3):
            np.testing.assert_allclose(path.at(t, order)[stationary_group], 0, atol=1e-8)
    for left, right in zip(path.segments[:-1], path.segments[1:]):
        for order in range(4):
            np.testing.assert_allclose(left.at(left.duration, order), right.at(0, order), atol=1e-8)
    for segment in path.segments:
        for indices, limit in groups:
            for order, bound in enumerate((limit.velocity, limit.acceleration, limit.jerk), 1):
                assert segment.maximum(order, indices) <= bound*1.00001


def test_retarget_preserves_current_derivatives():
    current = [[.02, .01, 0.], [.01, 0., 0.], [.1, 0., 0.]]
    path = plan([[0., 0., 0.], [.2, .1, .03]], initial_derivatives=current)
    for order, expected in enumerate(current, 1):
        np.testing.assert_allclose(path.at(0, order), expected, atol=1e-8)
        np.testing.assert_allclose(path.at(path.duration, order), 0., atol=1e-8)


def test_fixed_boundary_derivatives_fail_cleanly_when_retiming_diverges():
    # Measured descent endpoints can have small residual speed but nonzero
    # acceleration/jerk. Stretching this retarget previously overflowed its
    # polynomial roots, bypassing the adapter's continuous braking path.
    with pytest.raises(RuntimeError, match="retiming did not converge"):
        plan([[0., 0., 0.], [.5, 0., 0.]],
             initial_derivatives=([.005, 0., 0.], [.06, 0., 0.], [.6, 0., 0.]))


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


def test_vla_stop_keeps_measured_deceleration_instead_of_overshooting_workspace():
    # Original bowl pick 7819: cancelling deceleration first added 17.3 cm
    # along X and sent the screened stop beyond the available Panda IK.
    v = [.1377386821550182, -.04651157741674794, .17552906516569156]
    a = [.286002112616289, -.02010814317605636, -.4030441714937716]
    j = [-1.3031150603213248, 1.8152361670442652, -3.657378166932901]
    path = brake([0., 0., 0.], v, a, jerk=j)
    assert path.at(path.duration)[0] < .14
    for derivative, initial in enumerate(([0., 0., 0.], v, a, j)):
        np.testing.assert_allclose(path.at(0., derivative), initial, atol=1e-9)
    for left, right in zip(path.segments[:-1], path.segments[1:]):
        for derivative in range(4):
            np.testing.assert_allclose(left.at(left.duration, derivative), right.at(0., derivative), atol=1e-8)
    for derivative in (1, 2, 3):
        np.testing.assert_allclose(path.at(path.duration, derivative), 0., atol=1e-8)
    # The first interval retains measured jerk; later segments use nominal
    # jerk and only the acceleration already inherited from that interval.
    assert max(s.maximum(3, slice(None)) for s in path.segments[1:]) <= 2.00002
    inherited_acceleration = np.linalg.norm(path.segments[0].at(.05, 2))
    assert max(s.maximum(2, slice(None)) for s in path.segments[1:]) <= max(.5, inherited_acceleration)*1.00001


def test_free_endpoint_brake_shortens_an_outward_accelerating_vla_handoff():
    # Public control 67 of original bowl probe7843. The old stop added
    # 21.2cm along X and its route failed IK; a free endpoint need not do so.
    v = [.1462388649470603, -.023790793158474655, .15768653379578002]
    a = [.38569429534030253, -.17474740439172853, -.32528633388362316]
    j = [-2.0803929823183243, .5560944397124956, -3.52007096493967]
    path = brake([0., 0., 0.], v, a, jerk=j)
    assert path.at(path.duration)[0] < .19
    for order, initial in enumerate(([0., 0., 0.], v, a, j)):
        np.testing.assert_allclose(path.at(0., order), initial, atol=1e-8)
    for left, right in zip(path.segments[:-1], path.segments[1:]):
        for order in range(4):
            np.testing.assert_allclose(left.at(left.duration, order), right.at(0., order), atol=1e-8)
    for order in (1, 2, 3):
        np.testing.assert_allclose(path.at(path.duration, order), 0., atol=1e-8)
    inherited_acceleration = np.linalg.norm(path.segments[0].at(.05, 2))
    assert max(s.maximum(3, slice(None)) for s in path.segments[1:]) <= 2.00002
    assert max(s.maximum(2, slice(None)) for s in path.segments[1:]) <= max(.5, inherited_acceleration)*1.00001


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
