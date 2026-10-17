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


def test_shared_prefix_reuses_geometry_without_skipping_new_swept_collisions(monkeypatch):
    from robots.libero import bounded_screen

    count = []
    original = bounded_screen.collision_counts
    def measured(*args, **kwargs):
        count.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(bounded_screen, 'collision_counts', measured)
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    screen = PublicRouteScreen(np.array([[.05, 0., 1.]]), geometry, ik)
    start = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    assert screen([start])['passed']
    calls = len(count)
    assert screen([start])['passed'] and len(count) == calls
    blocked = screen([start, {**start, 'xyz_m': [.1, 0., 1.]}])
    assert not blocked['passed'] and blocked['reason'] == 'measured_sweep_collision'
    assert len(count) > calls
    # The timestamp belongs to this use of the cached geometry, not to a
    # previous trajectory which reached the same physical pose.
    point = {**blocked['at'], 'time_s': 12.}
    assert screen([point])['at']['time_s'] == 12.
    fresh = PublicRouteScreen(np.array([[0., 0., 1.]]), geometry, ik)
    assert fresh([start])['collision'] is True


def test_clearance_certificate_reduces_work_and_keeps_a_midroute_target_collision():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    poses = [{'xyz_m': [x, 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
             for x in np.linspace(0., .1, 101)]
    clear = PublicRouteScreen(np.array([[1., 1., 1.]]), geometry, ik)(poses)
    assert clear['passed']
    assert clear['geometry_evaluations'] < clear['samples']/3
    assert clear['clearance_certified_samples'] > 0
    blocked = PublicRouteScreen(np.array([[1., 1., 1.]]), geometry, ik,
        contact_points=np.array([[.05, 0., 1.]]))(poses)
    assert blocked['reason'] == 'measured_sweep_collision'
    assert blocked['target_counts']['palm'] == 1


def test_sweep_and_certificate_include_the_rotating_payload_extent():
    from scipy.spatial.transform import Rotation

    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    obstacle = Rotation.from_euler('z', .1).apply([.5, 0., 0.])+[0., 0., 1.]
    screen = PublicRouteScreen(np.array([obstacle]), geometry, ik, payload_local=[[.5, 0., 0.]])
    result = screen([{'xyz_m': [0., 0., 1.], 'quat_xyzw': Rotation.from_euler('z', a).as_quat()}
                     for a in [0., .2]])
    assert screen.radius >= .5
    assert result['reason'] == 'measured_payload_collision'
    assert result['path_min_clearance_m'] < .004


def test_certificate_keeps_axis_expanded_box_corner_collisions():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    # Initially beyond the x margin. After 2 mm of travel the point is in
    # all three expanded box axes, despite >4 mm Euclidean raw-box distance.
    poses = [{'xyz_m': [x, 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
             for x in [0., .002]]
    screen = PublicRouteScreen(np.array([[.0105, .0085, 1.0085]]), geometry, ik)
    assert screen._geometry_at(poses[0])['passed']
    assert screen(poses)['reason'] == 'measured_sweep_collision'
