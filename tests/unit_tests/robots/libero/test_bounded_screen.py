"""Measured target contact remains separate from scene obstacles."""
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from robots.libero.bounded_screen import PublicRouteScreen


def test_endpoint_screen_leaves_an_obstructed_connecting_path_unknown():
    geometry = {'boxes':[{'name':'palm','lower':[-.01]*3,'upper':[.01]*3}]}
    made = []
    def solver(robot):
        result = SimpleNamespace(check=lambda *args:{'solution_found':True})
        made.append(result)
        return result
    screen = PublicRouteScreen([[.1,0.,1.]], geometry,
        SimpleNamespace(with_measured_robot=solver,check=lambda *args:{'solution_found':True}))
    route = [{'xyz_m':[0.,0.,1.],'quat_xyzw':[0.,0.,0.,1.]},
             {'xyz_m':[.2,0.,1.],'quat_xyzw':[0.,0.,0.,1.]}]
    robot = {'joint_positions_rad':[0.]*7}
    cheap = screen.endpoint_screen(route,robot)
    assert cheap['passed'] and cheap['ik_reachable'] is True
    assert cheap['collision'] is None and cheap['path_min_clearance_m'] is None
    assert screen(route)['collision'] is True
    screen.endpoint_screen(list(reversed(route)),robot)
    assert screen.endpoint_screen(route,robot)==cheap
    assert len(made)==2 and made[0] is not made[1]
    assert all(s.warm_start is False for s in made)


def test_current_joint_seed_keeps_captured_scene_payload_and_margin_evidence():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    new_ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    received = []
    def measured(robot):
        received.append(robot)
        return new_ik
    old_ik = SimpleNamespace(with_measured_robot=measured)
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    screen = PublicRouteScreen([[.103, 0., 1.]], geometry, old_ik,
        payload_local=[[.1, 0., 0.]], initial_pose=pose)
    robot = {'joint_positions_rad': [.2]*7, 'eef_xyz_m': [.02, 0., 1.]}
    current = screen.with_measured_robot(robot)
    assert received == [robot] and current.ik is new_ik and screen.ik is old_ik
    assert current.points is screen.points and current.payload is screen.payload
    assert current.initial_payload_margin == screen.initial_payload_margin
    assert current._pose_geometry_cache is screen._pose_geometry_cache


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


def test_blocked_start_does_not_expand_the_unreachable_remaining_route(monkeypatch):
    from robots.libero import bounded_screen

    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    screen = PublicRouteScreen([[0., 0., 1.]], geometry,
        SimpleNamespace(check=lambda *args: {'solution_found': True}))
    monkeypatch.setattr(bounded_screen, 'Slerp', lambda *args: pytest.fail(
        'must reject occupied start before expanding its future route'))
    result = screen([{'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]},
                     {'xyz_m': [1000., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}])
    assert result['reason'] == 'measured_sweep_collision' and result['samples'] == 1


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


def test_contact_uses_each_finger_joint_instead_of_half_aperture():
    from robots.libero.bounded_self_filter import (
        gripper_at_measured_fingers,
        remove_current_gripper,
    )

    geometry = {'boxes': [
        {'name': 'leftfinger', 'lower': [-.001]*3, 'upper': [.001]*3,
         'slide_per_half_opening': [1., 0., 0.]},
        {'name': 'rightfinger', 'lower': [-.001]*3, 'upper': [.001]*3,
         'slide_per_half_opening': [-1., 0., 0.]}]}
    measured = gripper_at_measured_fingers(geometry, [.006, -.012])
    points = np.array([[.006, 0., 0.], [-.012, 0., 0.], [.009, .006, 0.]])
    # Choose body rotation whose grip-site rotation is identity.
    quat = Rotation.from_euler('z', np.pi/2).as_quat()
    retained, count = remove_current_gripper(points, [0., 0., 0.], quat, measured, .018)
    assert count == 2
    np.testing.assert_allclose(retained, points[-1:])
    assert geometry['boxes'][0]['lower'] == [-.001]*3
    assert PublicRouteScreen(points[-1:], measured,
        SimpleNamespace(check=lambda *args: {'solution_found': True}), opening=.018)(
            [{'xyz_m': [0., 0., 0.], 'quat_xyzw': quat.tolist()}])['passed']


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


def test_payload_can_leave_occupied_positive_margin_but_cannot_move_closer():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    screen = PublicRouteScreen([[.103, 0., 1.]], geometry, ik,
        payload_local=[[.1, 0., 0.]], initial_pose=pose)
    exit_route = screen([pose, {**pose, 'xyz_m': [-.02, 0., 1.]}])
    assert exit_route['passed']
    incursion = screen([pose, {**pose, 'xyz_m': [.001, 0., 1.]}])
    assert incursion['reason'] == 'measured_payload_collision'
    # An exact observed-surface intersection gets no starting allowance.
    intersecting = PublicRouteScreen([[.1, 0., 1.]], geometry, ik,
        payload_local=[[.1, 0., 0.]], initial_pose=pose)
    assert intersecting([pose])['reason'] == 'measured_payload_collision'


def test_payload_margin_checks_new_neighbours_even_when_nearest_pair_is_allowed():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    obstacles = [[.1, -.001, 1.], [.105, 0., 1.]]
    screen = PublicRouteScreen(obstacles, geometry, ik,
        payload_local=[[.1, 0., 0.]], initial_pose=pose)
    assert screen([pose])['passed']
    hit = screen([pose, {**pose, 'xyz_m': [.0015, 0., 1.]}])
    assert hit['reason'] == 'measured_payload_collision'
    np.testing.assert_allclose(hit['obstacle_point'], obstacles[1])


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


def test_existing_positive_margin_allows_escape_but_not_further_incursion():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    point = np.array([[.008, 0., 1.]])  # Outside the hull, inside its 4 mm margin.
    screen = PublicRouteScreen(point, geometry, ik, initial_pose=pose)
    escape = screen([pose, {**pose, 'xyz_m': [-.02, 0., 1.]}])
    assert escape['passed']
    toward = screen([pose, {**pose, 'xyz_m': [.001, 0., 1.]}])
    assert toward['reason'] == 'measured_sweep_collision'
    assert toward['public_scene_collision_points']['palm'] == point.tolist()
    # Reuse cannot convert the first candidate's endpoint to a new baseline.
    assert screen._geometry_at(pose)['initial_margin_pairs_retained'] == 1
    assert screen([pose])['passed']


def test_target_positive_margin_escape_matches_scene_without_allowing_new_contact():
    geometry = {'boxes': [{'name': 'rightfinger', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    target = [[.008, 0., 1.]]
    screen = PublicRouteScreen([[10., 10., 10.]], geometry, ik,
        contact_points=target, initial_pose=pose)
    assert screen([pose, {**pose, 'xyz_m': [-.02, 0., 1.]}])['passed']
    assert screen._geometry_at(pose)['initial_target_margin_pairs_retained'] == 1
    deeper = screen([pose, {**pose, 'xyz_m': [.001, 0., 1.]}])
    assert deeper['reason'] == 'measured_sweep_collision'
    assert deeper['target_counts']['rightfinger'] == 1
    for points in ([[.004, 0., 1.]], [[.008, 0., 1.], [-.02, 0., 1.]]):
        blocked = PublicRouteScreen([[10., 10., 10.]], geometry, ik,
            contact_points=points, initial_pose=pose)
        assert blocked([pose, {**pose, 'xyz_m': [-.02, 0., 1.]}])['collision']


def test_margin_escape_never_allows_mesh_interiors_or_new_obstacles():
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3, 'upper': [.005]*3}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.], 'quat_xyzw': [0., 0., 0., 1.]}
    physical_contact = PublicRouteScreen([[.004, 0., 1.]], geometry, ik, initial_pose=pose)
    assert physical_contact([pose])['collision']
    route = [pose, {**pose, 'xyz_m': [-.02, 0., 1.]}]
    obstacle = PublicRouteScreen([[.008, 0., 1.], [-.02, 0., 1.]], geometry, ik, initial_pose=pose)
    assert obstacle._geometry_at(pose)['passed']
    assert obstacle(route)['collision']


def test_margin_escape_uses_each_mesh_halfspace_and_rotated_pose():
    equations = [[1., 0., 0., -.005], [-1., 0., 0., -.005],
                 [0., 1., 0., -.005], [0., -1., 0., -.005],
                 [0., 0., 1., -.005], [0., 0., -1., -.005]]
    geometry = {'boxes': [{'name': 'palm', 'lower': [-.005]*3,
                          'upper': [.005]*3, 'convex_halfspaces': equations}]}
    ik = SimpleNamespace(check=lambda *args: {'solution_found': True})
    pose = {'xyz_m': [0., 0., 1.],
            'quat_xyzw': Rotation.from_euler('z', np.pi/2).as_quat().tolist()}
    screen = PublicRouteScreen([[.008, 0., 1.]], geometry, ik, initial_pose=pose)
    assert screen([pose, {**pose, 'xyz_m': [-.01, 0., 1.]}])['passed']
    assert screen([pose, {**pose, 'xyz_m': [.001, 0., 1.]}])['collision']
