"""The alternative ingress is based only on observed bounds and robot size."""
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_approach import elevated_approach


def test_obstacle_height_and_payload_radius_determine_a_shared_corridor():
    robot = {'eef_xyz_m':[0.,0.,.2], 'eef_quat_xyzw':[0.,0.,0.,1.]}
    endpoint = {'xyz_m':[.5,0.,.15], 'quat_xyzw':[1.,0.,0.,0.]}
    screen = SimpleNamespace(radius=.1, points=np.array([[.25,0.,.6],[5.,5.,9.]]), target=np.empty((0,3)))
    route, evidence = elevated_approach(robot, endpoint, screen)
    assert np.isclose(route[0]['xyz_m'][2], .704)
    assert route[0]['xyz_m'][:2] == [0.,0.] and route[0]['quat_xyzw'] == robot['eef_quat_xyzw']
    assert route[1]['xyz_m'] == [.5,0.,route[0]['xyz_m'][2]]
    assert route[-1] == endpoint
    assert evidence['corridor_points'] == 1 and not evidence['private_pose_used']
    screen.radius = .2
    larger, _ = elevated_approach(robot, endpoint, screen)
    assert larger[0]['xyz_m'][2] > route[0]['xyz_m'][2]


def test_empty_measurement_retains_screen_requirement_and_measured_endpoint():
    robot = {'eef_xyz_m':[0.,0.,.5], 'eef_quat_xyzw':[0.,0.,0.,1.]}
    endpoint = {'xyz_m':[.1,.2,.3]}
    screen = SimpleNamespace(radius=.12, points=np.empty((0,3)), target=np.empty((0,3)))
    route, evidence = elevated_approach(robot, endpoint, screen)
    assert route[-1]['xyz_m'] == endpoint['xyz_m']
    assert evidence['requires_unchanged_full_route_screen']
    assert route[0]['xyz_m'][2] > robot['eef_xyz_m'][2]
