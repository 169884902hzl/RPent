"""Full-route regressions: clear endpoints do not establish a clear route."""
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_grasp_route import sweep_route, separate_target_points, approach_route


class PoseScreen:
    def __init__(self, forbidden=None):
        self.forbidden = forbidden

    def check(self, xyz, quat):
        valid = self.forbidden is None or not self.forbidden(xyz)
        return {'solution_found': valid, 'source': 'test_public_proprioception'}


def geometry():
    return {'boxes': [{'name': 'hand', 'lower': [-.01]*3, 'upper': [.01]*3}]}


def route():
    return [{'phase': 'route_contact', 'xyz': [.2,0,1],
             'body_quat_xyzw': Rotation.identity().as_quat().tolist()}]


def test_thin_obstacle_between_clear_endpoints_rejects_swept_route():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.array([[.1,0,1]]),
                               np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is False
    assert result['reason']=='approach_sweep_collision'
    assert 0 < result['segments'][0]['collision']['fraction'] < 1


def test_blocked_route_is_rejected_before_running_ik():
    class NoIK:
        def check(self, xyz, quat):
            raise AssertionError('a blocked route does not need IK')

    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.array([[.19,0,1]]),
                               np.empty((0,3)),geometry(),pose_screen=NoIK())
    assert not valid
    assert result['reason'] == 'approach_sweep_collision'


def test_intermediate_ik_failure_rejects_reachable_endpoints():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.empty((0,3)),
                               np.empty((0,3)),geometry(),
                               pose_screen=PoseScreen(lambda xyz:.07<xyz[0]<.13))
    assert valid is False
    assert result['reason']=='approach_route_ik_not_found'


def test_execution_uses_only_screened_waypoints_and_includes_contact_endpoint():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.empty((0,3)),
                               np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is True
    assert result['execution_waypoints'][-1]['xyz']==[.2,0,1]
    assert result['execution_waypoints'][-1]['contact_endpoint'] is True
    assert len(result['execution_waypoints'])==len(result['segments'][0]['ik_checks'])


def test_neighbour_within_old_carving_radius_is_kept_as_obstacle():
    target = np.array([[0., 0., 1.]])
    scene = np.array([[0., 0., 1.], [0., 0., 1.005]])
    _, obstacles = separate_target_points(target, scene)
    assert np.allclose(obstacles, [[0., 0., 1.005]])


def test_scene_voxel_cannot_merge_target_pixel_and_adjacent_obstacle():
    target = np.array([[.0001, 0., 1.]])
    scene = np.array([[.0001, 0., 1.], [.002, 0., 1.]])
    _, obstacles = separate_target_points(target, scene)
    assert np.allclose(obstacles, [[.002, 0., 1.]])


def test_side_route_can_rotate_at_lower_pregrasp_without_assuming_high_wrist_reachable():
    start_quat = [1.,0.,0.,0.]
    side_quat = Rotation.from_euler('y', np.pi/2).as_quat().tolist()
    path = approach_route([0,0,1.2], start_quat, [.2,0,.95], side_quat,
                          'side_1', [.05,0,.95], 1.2, orient_at_pregrasp=True)
    assert path[1]['body_quat_xyzw'] == start_quat
    assert path[2]['body_quat_xyzw'] == start_quat
    assert path[3]['phase'] == 'route_orient_at_pregrasp'
    assert path[3]['xyz'] == path[2]['xyz']
    assert path[3]['body_quat_xyzw'] == side_quat
    assert path[-1]['phase'] == 'route_contact'
    valid, evidence = sweep_route([0,0,1.2], start_quat, path, np.empty((0,3)),
        np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is True
    assert any('route_orient_at_pregrasp' in w['phase'] for w in evidence['execution_waypoints'])
