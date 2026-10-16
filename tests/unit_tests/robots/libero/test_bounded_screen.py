"""Measured target contact remains separate from scene obstacles."""
from types import SimpleNamespace
import numpy as np
from robots.libero.bounded_screen import PublicRouteScreen


def test_target_broad_phase_keeps_real_collisions_and_allowed_finger_contact():
    geometry = {"boxes": [
        {"name": "palm", "lower": [-.02, -.02, .04], "upper": [.02, .02, .06]},
        {"name": "left_pad", "lower": [-.02, -.02, -.01], "upper": [.02, .02, .01]}]}
    ik = SimpleNamespace(check=lambda xyz, quat: {"solution_found": True})
    # Large distant mask must not hide the one pixel that intersects a pad.
    target = np.r_[np.full((10000, 3), 10.), [[0., 0., 0.]]]
    scene = np.array([[1., 1., 1.]])
    pose = [{"xyz_m": [0., 0., 0.], "quat_xyzw": [0., 0., 0., 1.]}]
    blocked = PublicRouteScreen(scene, geometry, ik, contact_points=target)(pose)
    allowed = PublicRouteScreen(scene, geometry, ik, contact_points=target, contact_allowed=True)(pose)
    assert blocked["reason"] == "measured_sweep_collision"
    assert blocked["target_counts"]["left_pad"] == 1
    assert allowed["passed"]
    obstacle = PublicRouteScreen(np.array([[0., 0., 0.]]), geometry, ik,
        contact_points=target, contact_allowed=True)(pose)
    assert obstacle["collision"] and obstacle["counts"]["left_pad"] == 1
    assert obstacle['public_scene_collision_points']['left_pad'] == [[0., 0., 0.]]


def test_current_gripper_filter_keeps_five_mm_obstacle_in_future_route():
    from robots.libero.bounded_self_filter import remove_current_gripper

    geometry = {'boxes': [{'name': 'palm', 'lower': [-.02]*3, 'upper': [.02]*3}]}
    points = np.array([[0., 0., 1.], [0., 0., 1.025]])
    target, count = remove_current_gripper(points, [0., 0., 1.], [0., 0., 0., 1.], geometry, .08)
    assert count == 1
    np.testing.assert_allclose(target, points[1:])
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    result = PublicRouteScreen(np.array([[1., 1., 1.]]), geometry, ik, contact_points=target)(
        [{'xyz_m': [0., 0., 1.006], 'quat_xyzw': [0., 0., 0., 1.]}])
    assert result['collision'] and result['target_counts']['palm'] == 1
