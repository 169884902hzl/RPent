import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_payload import moving_payload_pixels


def test_payload_edge_requires_rigid_motion_and_keeps_stationary_neighbour():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    target = np.array([[0., 0., 0.], [.01, 0., 0.]])
    # This neighbour lies inside the 4 mm surface residual after the lift;
    # matching the old stationary scene must prevent its removal.
    neighbour = [.002, 0., .1]
    ref = {'target': target, 'scene': np.vstack([target, neighbour]),
           'robot': robot, 'capture_step': 7}
    current = {**robot, 'eef_xyz_m': [0., 0., .1]}
    points = np.array([[.01, 0., .101], neighbour, [.015, 0., .1]])
    matched, evidence = moving_payload_pixels(points, ref, current)
    assert matched.tolist() == [True, False, False]
    assert evidence['stationary_points_retained'] == 1
    assert evidence['private_pose_used'] is False


def test_payload_tracks_measured_rotation_and_retains_unmoved_surface():
    old = {'eef_xyz_m': [1., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    target = np.array([[1.02, 0., 0.]])
    ref = {'target': target, 'scene': target, 'robot': old, 'capture_step': 2}
    current = {'eef_xyz_m': [1., 0., .1],
               'eef_quat_xyzw': Rotation.from_euler('z', 90, degrees=True).as_quat().tolist()}
    matched, _ = moving_payload_pixels([[1., .02, .1], [1.02, 0., 0.]], ref, current)
    assert matched.tolist() == [True, False]


def test_no_motion_does_not_relabel_nearby_obstacles_as_payload():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    ref = {'target': [[0., 0., 0.]], 'scene': [[0., 0., 0.]],
           'robot': robot, 'capture_step': 1}
    matched, _ = moving_payload_pixels([[.002, 0., 0.]], ref, robot)
    assert not matched.any()
