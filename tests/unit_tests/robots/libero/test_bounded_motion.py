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


def test_rejected_brake_is_not_reported_as_a_smooth_stop():
    p = FakePrimitives()
    calls = []
    def screen(poses):
        calls.append(True)
        return {"passed": len(calls) == 1, "reason": "rejected_brake"}
    result = SmoothMotion(p, screen).run([{"xyz_m": [.1, 0., 1.]}], contact_stop=lambda _: True)
    assert result["stop_reason"] == "braking_screen_rejected"
    assert result["braking"]["steps_used"] == 0


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
