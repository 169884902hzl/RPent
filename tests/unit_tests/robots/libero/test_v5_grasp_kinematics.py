from pathlib import Path

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from robots.libero.v5_grasp_kinematics import PublicPoseScreen, forward, robot_chain, robot_link_hulls


def robot_fixture():
    import robosuite
    path = Path(robosuite.__file__).parent / 'models/assets/robots/panda/robot.xml'
    model = mujoco.MjModel.from_xml_path(str(path))
    body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_hand')
    addresses = [model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f'joint{i+1}')]
                 for i in range(7)]
    return path, model, body, addresses


def measured_pose(model, body, addresses, joints):
    data = mujoco.MjData(model)
    data.qpos[addresses] = joints
    mujoco.mj_forward(model, data)
    rotation = data.xmat[body].reshape(3, 3)
    return data.xpos[body] + rotation @ [0., 0., .097], Rotation.from_matrix(rotation).as_quat(), data


def test_static_robot_chain_matches_installed_robot_over_joint_configurations():
    path, model, body, addresses = robot_fixture()
    nodes, limits, _ = robot_chain(str(path))
    rng = np.random.default_rng(170609911)
    for joints in rng.uniform(limits[:, 0]+.1, limits[:, 1]-.1, (10, 7)):
        _, _, data = measured_pose(model, body, addresses, joints)
        pose = forward(nodes, joints)
        assert np.allclose(pose[:3, 3], data.xpos[body], atol=1e-9)
        assert np.allclose(pose[:3, :3], data.xmat[body].reshape(3, 3), atol=1e-9)


def test_analytic_site_and_rotation_error_jacobians_match_finite_differences():
    from robots.libero.v5_grasp_kinematics import forward_jacobian, rotation_error_jacobian
    path, model, body, addresses = robot_fixture()
    nodes, limits, _ = robot_chain(str(path))
    rng = np.random.default_rng(16102026)
    for joints in rng.uniform(limits[:, 0]+.1, limits[:, 1]-.1, (5, 7)):
        pose, site, jac = forward_jacobian(nodes, joints, np.array([0., 0., .097]))
        desired = Rotation.from_rotvec([.6, -.5, .4])*Rotation.from_matrix(pose[:3, :3])
        error = (desired*Rotation.from_matrix(pose[:3, :3]).inv()).as_rotvec()
        expected = np.r_[jac[:3], -rotation_error_jacobian(error)@jac[3:]]
        def residual(q):
            t = forward(nodes, q)
            return np.r_[t[:3, 3]+t[:3, :3]@[0., 0., .097]-site,
                (desired*Rotation.from_matrix(t[:3, :3]).inv()).as_rotvec()]
        numerical = np.column_stack([(residual(joints+np.eye(7)[i]*1e-6)
            -residual(joints-np.eye(7)[i]*1e-6))/(2e-6) for i in range(7)])
        np.testing.assert_allclose(expected, numerical, atol=1e-7)


def test_public_pose_screen_finds_known_measured_pose_and_rejects_distant_pose():
    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, _ = measured_pose(model, body, addresses, joints)
    screen = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097])
    nearby, nearby_quat, _ = measured_pose(model, body, addresses, joints + [.04, 0., 0., 0., 0., .02, 0.])
    attainable = screen.check(nearby, nearby_quat)
    assert attainable['solution_found']
    assert attainable['solves'][-1]['position_error_m'] < .008
    assert attainable['source'] == 'static_robot_description_and_public_proprioception'
    distant = screen.check(np.asarray(xyz) + [4., 0., 0.], quat)
    assert not distant['solution_found']
    assert distant['numerical_failure_is_not_proof_of_infeasibility']
    assert distant['arm_collisions_checked'] is False


def test_missing_joint_proprioception_is_not_replaced_with_scene_truth():
    path, _, _, _ = robot_fixture()
    with pytest.raises(ValueError, match='seven measured public robot joint positions'):
        PublicPoseScreen(path, [0.], [0., 0., 1.], [0., 0., 0., 1.], [0., 0., .097])


def test_dense_warm_route_keeps_the_same_ik_acceptance_tolerances():
    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, _ = measured_pose(model, body, addresses, joints)
    screen = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097], warm_start=True)
    for offset in np.linspace(0., .2, 15):
        target, orientation, _ = measured_pose(model, body, addresses, joints+[offset, 0., 0., 0., 0., 0., 0.])
        result = screen.check(target, orientation)
        assert result["solution_found"]
        assert result["solves"][-1]["position_error_m"] < .008
        assert result["solves"][-1]["orientation_error_rad"] < .05


def test_wrist_robot_surface_is_removed_but_nearby_scene_point_remains():
    path, model, body, addresses = robot_fixture()
    joints = np.array([.2, -.4, .3, -2.2, .1, 2., .6])
    xyz, quat, data = measured_pose(model, body, addresses, joints)
    screen = PublicPoseScreen(path, joints, xyz, quat, [0., 0., .097])
    hull = next(hull for hull in robot_link_hulls(str(path)) if hull['name']=='link7')
    from robots.libero.v5_geometric_grasp import stl_vertices
    vertices = stl_vertices(hull['mesh']['path'])
    # The farthest X vertex is on the true wrist surface. A scene surface
    # 1 cm farther out is beyond its mesh, and must not be carved away.
    surface = vertices[np.argmax(vertices[:,0])]
    neighbour = surface + [.01, 0., 0.]
    link = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'link7')
    rotation = data.xmat[link].reshape(3,3)
    points = np.array([surface, neighbour])@rotation.T+data.xpos[link]
    retained, evidence = screen.remove_measured_arm(points)
    assert np.allclose(retained, points[1:])
    assert evidence['per_link']['link7']==1
    assert evidence['future_arm_collisions_checked'] is False
