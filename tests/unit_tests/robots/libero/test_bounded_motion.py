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
