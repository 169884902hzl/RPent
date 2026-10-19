# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Kinematic guides retain a separate contact route and measured-only inputs."""

from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_joint_routes import contact_guides
from robots.libero.v5_grasp_kinematics import PublicPoseScreen
from tests.unit_tests.robots.libero.test_v5_grasp_kinematics import (
    measured_pose,
    robot_fixture,
)


def test_public_kinematic_guide_splits_before_contact_without_mutating_ik():
    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, _ = measured_pose(model, body, addresses, joints)
    goal, orientation, _ = measured_pose(model, body, addresses, joints+[.5, 0., 0., 0., 0., 0., 0.])
    ik = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097], warm_start=True)
    before = (ik.last_solution, dict(ik.cache), ik.route_joint_step_rad)
    candidate = {'xyz_m': goal, 'quat_xyzw': orientation, 'path': 'direct', 'screen': {'passed': False}}
    guide, = list(contact_guides(SimpleNamespace(ik=ik),
        {'joint_positions_rad': joints}, [candidate, candidate]))
    assert guide['route'] == guide['approach_route']+guide['contact_route']
    np.testing.assert_allclose(guide['route'][-1]['xyz_m'], goal)
    assert np.linalg.norm(np.asarray(guide['approach_xyz_m'])-goal) >= .04
    assert guide['screen'] is None  # A guide is not a passed collision/IK screen.
    assert (ik.last_solution, ik.cache, ik.route_joint_step_rad) == before


def test_unreachable_or_endpoint_closure_collision_has_no_guide():
    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, _ = measured_pose(model, body, addresses, joints)
    ik = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097], warm_start=True)
    candidates = [{'xyz_m': np.asarray(xyz)+[4., 0., 0.], 'quat_xyzw': quat},
        {'xyz_m': xyz, 'quat_xyzw': quat, 'closure': {'scene': {'palm': 1}}}]
    assert not list(contact_guides(SimpleNamespace(ik=ik), {'joint_positions_rad': joints}, candidates))
