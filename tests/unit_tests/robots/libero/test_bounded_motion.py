"""Adapter produces OSC vector commands and screens the blended curve."""
import numpy as np

from robots.libero.bounded_motion import SmoothMotion


class FakeEnv:
    terminated = truncated = False
    def __init__(self):
        self.position = np.array([0., 0., 1.])
    def raw_obs(self):
        return {"robot0_eef_pos": self.position, "robot0_eef_quat": [0, 0, 0, 1],
                "robot0_gripper_qpos": [.04, -.04], "robot0_joint_pos": np.zeros(7)}


class FakePrimitives:
    def __init__(self):
        self.env = FakeEnv()
        self.actions = []
    def _step_env(self, action):
        self.actions.append(action)
        self.env.position += action[:3]*.05


def test_contact_handoff_damps_without_a_new_sweep_or_releasing_payload():
    from robots.libero.bounded_motion import settle_osc_hold

    p = FakePrimitives()
    velocity = .2
    def damp(action):
        nonlocal velocity
        p.actions.append(action)
        p.env.position[0] += velocity*.05
        velocity *= .5
    p._step_env = damp
    result = settle_osc_hold(p, 1.)
    assert result['completed'] and result['settled']
    assert result['reason'] == 'osc_damped_hold'
    assert all(np.array_equal(action, [0, 0, 0, 0, 0, 0, 1]) for action in p.actions)
    speeds = [row['velocity_m_s'] for row in result['trace']]
    assert all(b <= a for a, b in zip(speeds, speeds[1:]))
    assert p._bounded_rest_reference['measured_robot']['eef_xyz_m'] == p.env.position.tolist()
    actions_before = len(p.actions)
    denied = SmoothMotion(p, lambda _: {'passed': False, 'reason': 'blocked'}).run(
        [{'xyz_m': [.2, 0., 1.]}])
    assert not denied['executed'] and len(p.actions) == actions_before


def test_contact_handoff_that_does_not_settle_is_explicitly_incomplete():
    from robots.libero.bounded_motion import MotionConfig, settle_osc_hold

    p = FakePrimitives()
    p._step_env = lambda _: setattr(p.env, 'position', p.env.position+[.01, 0., 0.])
    result = settle_osc_hold(p, -1., MotionConfig(handoff_max_steps=3))
    assert not result['completed'] and result['reason'] == 'hold_not_settled'
    assert not hasattr(p, '_bounded_rest_reference')


def test_executes_blended_curve_and_reports_actual_metrics():
    p = FakePrimitives()
    seen = []
    def screen(poses):
        seen.extend(poses)
        return {"passed": True, "reason": "tested"}
    result = SmoothMotion(p, screen).run([{"xyz_m": [.1, .1, 1.]}, {"xyz_m": [.2, .1, 1.]}])
    assert result["executed"] and result["endpoint_error_m"] < 1e-10
    assert result["metrics"]["waypoint_stops"] == 0
    assert len(seen) > 20
    assert max(np.linalg.norm(action[:3]) for action in p.actions) < 1.


def test_adjacent_references_do_not_reset_to_feedback_lag_acceleration():
    from robots.libero.bounded_motion import measured_derivatives

    p = FakePrimitives()
    p._step_env = lambda action: setattr(p.env, 'position', p.env.position+action[:3]*.05*.15)
    screens = []
    def screen(poses):
        screens.append(poses)
        return {'passed': True}
    motion = SmoothMotion(p, screen)
    first = motion.run([{'xyz_m': [.1, 0., 1.]}])
    assert first['stop_reason'] == 'endpoint'
    assert np.linalg.norm(measured_derivatives(p, 20.)[1]) > 1e-5
    reference = first['trace'][-1]['desired']
    second = motion.run([{'xyz_m': [.15, .03, 1.]}])
    assert second['initial_derivatives_source'] == 'previous_rest_reference'
    np.testing.assert_allclose(screens[-1][0]['xyz_m'], first['trace'][-1]['after']['eef_xyz_m'])
    np.testing.assert_allclose(screens[-1][1]['xyz_m'], reference['xyz_m'])
    np.testing.assert_allclose(second['reference_start_pose']['eef_xyz_m'], reference['xyz_m'], atol=1e-12)
    np.testing.assert_allclose(second['reference_start_pose']['eef_quat_xyzw'], reference['quat_xyzw'], atol=1e-12)
    np.testing.assert_allclose(second['initial_derivatives'][:2], 0., atol=1e-12)
    np.testing.assert_allclose(first['trace'][-1]['reference_acceleration'], 0., atol=1e-9)
    assert second['metrics']['reference_max_jerk_limit_ratio'] <= 1.000001


def test_intervening_public_control_invalidates_a_rest_reference():
    from robots.libero.bounded_motion import public_control

    p = FakePrimitives()
    motion = SmoothMotion(p, lambda poses: {'passed': True})
    motion.run([{'xyz_m': [.1, 0., 1.]}])
    public_control(p, np.array([0., 0., 0., 0., 0., 0., 1.]))
    start, _, source = motion._reference_start(None)
    assert source == 'public_20hz_sensor_stream'
    np.testing.assert_allclose(start['eef_xyz_m'], p.env.position)


def test_rejected_inherited_brake_is_screened_before_planning_its_retarget(monkeypatch):
    from robots.libero import bounded_motion

    p = FakePrimitives()
    def suffix(*args, **kwargs):
        raise AssertionError('cannot retarget after a stop that has not passed screening')
    monkeypatch.setattr(bounded_motion, 'plan', suffix)
    motion = SmoothMotion(p, lambda poses: {'passed': False, 'reason': 'measured_sweep_collision'})
    *_, result = motion.prepare([{'xyz_m': [.01, 0., 1.]}],
        initial_derivatives=(np.array([.5, 0., 0., 0., 0., 0.]), np.zeros(6), np.zeros(6)))
    assert not result['passed'] and not p.actions


def test_one_tick_lead_uses_the_screened_curve_and_reduces_tracking_lag():
    from robots.libero.bounded_motion import MotionConfig

    results = []
    for lead_s in (0., .05):
        p = FakePrimitives()
        def lagged_step(action):
            p.actions.append(action)
            p.env.position += action[:3]*.05*.18
        p._step_env = lagged_step
        motion = SmoothMotion(p, lambda poses: {'passed': True}, MotionConfig(reference_lead_s=lead_s))
        trajectory, _, _, _ = motion.prepare([{'xyz_m': [.25, 0., 1.]}])
        result = motion.run([{'xyz_m': [.25, 0., 1.]}])
        results.append(result)
        for row in result['trace']:
            if row['braking']:
                continue
            command = row['command_reference']
            assert row['time_s'] <= command['time_s'] <= trajectory.duration
            np.testing.assert_allclose(command['xyz_m'], trajectory.at(command['time_s'])[:3], atol=1e-10)
    assert results[0]['stop_reason'] == 'tracking_error'
    assert results[1]['stop_reason'] == 'endpoint'
    assert results[1]['max_tracking_error_m'] < results[0]['max_tracking_error_m']


def test_rejected_curve_sends_no_physical_command():
    p = FakePrimitives()
    result = SmoothMotion(p, lambda poses: {"passed": False, "reason": "measured_sweep_collision"}).run([{"xyz_m": [.1, .1, 1.]}])
    assert result["steps_used"] == 0 and not p.actions


def test_second_tick_interruption_keeps_measured_velocity():
    p = FakePrimitives()
    checks = []
    def contact(_):
        checks.append(True)
        return len(checks) == 2
    result = SmoothMotion(p, lambda poses: {"passed": True, "reason": "tested"}).run(
        [{"xyz_m": [.1, 0., 1.]}], contact_stop=contact)
    assert result["braking"]["executed"]
    assert result["braking"]["initial_derivatives"]["velocity"][0] > 0.
    assert result["braking"]["steps_used"] > 0


def test_interrupt_brake_preserves_commanded_position_velocity_and_acceleration():
    from robots.libero.bounded_motion import MotionConfig, measured_derivatives
    from rpent.skill_package.trajectory import brake

    p = FakePrimitives()
    p._step_env = lambda action: setattr(p.env, 'position', p.env.position+action[:3]*.05*.3)
    checks, screens = [], []
    def contact(_):
        checks.append(True)
        return len(checks) == 6
    def screen(poses):
        screens.append(poses)
        return {'passed': True}
    config = MotionConfig(tracking_error_stop_m=.2)
    result = SmoothMotion(p, screen, config).run([{'xyz_m': [.1, 0., 1.]}], contact_stop=contact)
    tail = result['braking']
    assert tail['executed'] and tail['completed']
    previous = next(row for row, following in zip(result['trace'], result['trace'][1:])
                    if not row['braking'] and following['braking'])
    assert np.linalg.norm(np.array(previous['after']['eef_xyz_m'])-previous['command_reference']['xyz_m']) > 1e-5
    np.testing.assert_allclose(tail['reference_start_pose']['eef_xyz_m'],
                               previous['command_reference']['xyz_m'], atol=1e-12)
    for name in ('velocity', 'acceleration', 'jerk'):
        np.testing.assert_allclose(tail['initial_derivatives'][name],
                                   previous['command_reference_'+name], atol=1e-12)
    assert tail['initial_derivatives_source'] == 'last_command_reference'
    np.testing.assert_allclose(screens[-1][0]['xyz_m'], previous['after']['eef_xyz_m'])
    np.testing.assert_allclose(screens[-1][1]['xyz_m'], previous['command_reference']['xyz_m'])
    initial = tail['initial_derivatives']
    for axes, limit in config.groups():
        trajectory = brake(np.array(tail['reference_start_pose']['eef_xyz_m'])[axes]
            if axes.start == 0 else np.zeros(3), np.array(initial['velocity'])[axes],
            np.array(initial['acceleration'])[axes], jerk=np.array(initial['jerk'])[axes], limits=limit)
        assert max(segment.maximum(3, slice(None)) for segment in trajectory.segments) <= limit.jerk*1.000001
    assert measured_derivatives(p, config.hz) is not None


def test_rejected_brake_is_not_reported_as_a_smooth_stop():
    p = FakePrimitives()
    calls = []
    def screen(poses):
        calls.append(True)
        return {"passed": len(calls) == 1, "reason": "rejected_brake"}
    result = SmoothMotion(p, screen).run([{"xyz_m": [.1, 0., 1.]}], contact_stop=lambda _: True)
    assert result["stop_reason"] == "braking_screen_rejected"
    assert result["braking"]["steps_used"] == 0


def test_braking_screen_receives_post_motion_joint_measurements():
    p = FakePrimitives()
    original = p.env.raw_obs
    p.env.raw_obs = lambda: {**original(), 'robot0_joint_pos': np.full(7, len(p.actions)*.1)}
    measured = []
    class Screen:
        def __call__(self, poses):
            return {'passed': True}
        def with_measured_robot(self, robot):
            measured.append(robot)
            return lambda poses: {'passed': True}
    checks = []
    def contact(_):
        checks.append(True)
        return len(checks) == 2
    result = SmoothMotion(p, Screen()).run([{'xyz_m': [.1, 0., 1.]}], contact_stop=contact)
    assert result['braking']['executed']
    assert len(measured) == 1
    np.testing.assert_allclose(measured[0]['joint_positions_rad'], [.2]*7)
    np.testing.assert_allclose(measured[0]['eef_xyz_m'], result['trace'][1]['after']['eef_xyz_m'])


def test_rotation_is_braked_without_an_angular_velocity_reset():
    from scipy.spatial.transform import Rotation
    p = FakePrimitives()
    p.env.quat = Rotation.from_rotvec([0., 0., .02]).as_quat()
    original_obs = p.env.raw_obs
    p.env.raw_obs = lambda: {**original_obs(), "robot0_eef_quat": p.env.quat}
    def step(action):
        p.actions.append(action)
        p.env.position += action[:3]*.05
        p.env.quat = (Rotation.from_rotvec(action[3:6]*.5)*Rotation.from_quat(p.env.quat)).as_quat()
    p._step_env = step
    trace = []
    for index in range(4):
        before = {"eef_xyz_m": [0., 0., 1.], "eef_quat_xyzw": Rotation.from_rotvec([0., 0., index*.005]).as_quat()}
        after = {"eef_xyz_m": [0., 0., 1.], "eef_quat_xyzw": Rotation.from_rotvec([0., 0., (index+1)*.005]).as_quat()}
        trace.append({"before": before, "after": after, "time_s": (index+1)/20})
    result = SmoothMotion(p, lambda poses: {"passed": True})._brake(trace, -1.)
    assert result["executed"]
    np.testing.assert_allclose(result["initial_derivatives"]["velocity"][3:], [0., 0., .1], atol=1e-9)
    assert p.actions[0][5] > 0.


def test_visual_self_filter_removes_raster_edge_but_keeps_scene(monkeypatch):
    from types import SimpleNamespace
    from scipy.spatial import ConvexHull
    from robots.libero.bounded_self_filter import remove_visual_robot

    cube = np.array([[x, y, z] for x in (-.05, .05) for y in (-.05, .05) for z in (-.05, .05)])
    hull = (0, "static_visual", cube.min(0), cube.max(0), ConvexHull(cube).equations)
    monkeypatch.setattr("robots.libero.bounded_self_filter.visual_hulls", lambda path: [hull])
    ik = SimpleNamespace(world_offset=np.zeros(3), world_rotation=np.eye(3),
        nodes=[(np.eye(4), None)], joints=[], reference={"path": "test_static_description"})
    points = np.array([[.0523, 0, 0], [.06, 0, 0], [.2, .2, 0]])
    kept, evidence = remove_visual_robot(points, ik)
    np.testing.assert_equal(kept, points[1:])
    assert evidence["removed_points"] == 1


def test_next_motion_automatically_inherits_public_motion_derivatives():
    from robots.libero.bounded_motion import public_control, measured_derivatives

    p = FakePrimitives()
    for _ in range(4):
        public_control(p, np.array([.02, 0., 0., 0., 0., 0., -1.]))
    inherited = measured_derivatives(p, 20.)
    np.testing.assert_allclose(inherited[0], [.02, 0., 0., 0., 0., 0.], atol=1e-10)
    result = SmoothMotion(p, lambda poses: {'passed': True}).run([{'xyz_m': [.1, 0., 1.]}])
    assert result['initial_derivatives_source'] == 'public_20hz_sensor_stream'
    np.testing.assert_allclose(result['initial_derivatives'][0], inherited[0])


def test_inherited_overspeed_brakes_continuously_before_new_route():
    from robots.libero.bounded_motion import public_control

    p = FakePrimitives()
    for _ in range(4):
        public_control(p, np.array([.3, 0., 0., 0., 0., 0., -1.]))
    trajectory, _, poses, _ = SmoothMotion(p, lambda poses: {'passed': True}).prepare([{'xyz_m': [.2, 0., 1.]}])
    np.testing.assert_allclose(trajectory.at(0., 1), [.3, 0., 0., 0., 0., 0.], atol=1e-8)
    np.testing.assert_allclose(trajectory.at(trajectory.duration, 1), np.zeros(6), atol=1e-8)
    np.testing.assert_allclose(poses[-1]['xyz_m'], [.2, 0., 1.], atol=1e-8)


def test_nonconvergent_measured_retarget_brakes_before_replanning():
    p = FakePrimitives()
    derivatives = ([.005, 0., 0., 0., 0., 0.], [.06, 0., 0., 0., 0., 0.], [.6, 0., 0., 0., 0., 0.])
    trajectory, _, poses, screen = SmoothMotion(p, lambda poses: {'passed': True}).prepare(
        [{'xyz_m': [.5, 0., 1.]}], initial_derivatives=derivatives)
    assert screen['passed']
    for order, expected in enumerate(derivatives, 1):
        np.testing.assert_allclose(trajectory.at(0., order), expected, atol=1e-8)
        np.testing.assert_allclose(trajectory.at(trajectory.duration, order), np.zeros(6), atol=1e-8)
    np.testing.assert_allclose(poses[-1]['xyz_m'], [.5, 0., 1.], atol=1e-8)


def test_failed_waypoint_guard_brakes_before_unexecuted_suffix():
    p = FakePrimitives()
    checked = []
    def check(index, after):
        checked.append(index)
        return 'diagnostic_guard' if index == 0 else None
    result = SmoothMotion(p, lambda poses: {'passed': True, 'reason': 'public_test_scene'}).run(
        [{'xyz_m': [.1, 0., 1.]}, {'xyz_m': [.4, 0., 1.]}], waypoint_check=check)
    assert checked == [0]
    assert result['stop_reason'] == 'expected_receipt_diagnostic_guard'
    assert result['braking']['executed']
    assert result['steps_used'] == len(p.actions) == len(result['trace'])
    assert p.env.position[0] < .4
    assert result['metrics']['reference_max_translation_acceleration_jump'] < 1e-9
    assert result['metrics']['reference_max_jerk_limit_ratio'] <= 1.000001
