import numpy as np

from robots.libero.v5_geometric_grasp import (
    _opposition, _voxel, collision_counts, sample_grasps, servo_grasp_pose, side_site_rotation, site_rotation,
)


def test_voxel_retains_first_pixels_in_input_order_across_negative_and_positive_cells():
    points = np.array([
        [.0041, .0081, .0121], [-.0001, -.0041, .0161],
        [.0049, .0089, .0129], [-.0009, -.0049, .0169],
        [0., 0., 0.], [np.nan, 1., 1.], [1., np.inf, 1.],
        [-.0041, -.0041, .0161], [.0041, .0121, .0081],
        [.008, .0081, .0121], [1e-8, 0., 0.],
    ])
    expected = points[[0, 1, 7, 8, 9]]
    # Also exercise a view whose three coordinate columns are not contiguous.
    padded = np.zeros((len(points), 6))
    padded[:, ::2] = points
    np.testing.assert_array_equal(_voxel(padded[:, ::2]), expected)
    assert _voxel(np.empty((0, 3))).shape == (0, 3)
    assert _voxel(points[4:7]).shape == (0, 3)


def cube_surface():
    rng = np.random.default_rng(105)
    points = []
    for axis in range(3):
        for sign in (-1, 1):
            part = rng.uniform([-.025, -.017, .90], [.025, .017, .96], (4000, 3))
            part[:, axis] = ([.025, .017][axis] * sign if axis < 2 else .96 if sign > 0 else .90)
            points.append(part)
    return np.concatenate(points)


def gripper_geometry():
    return {'boxes': [
        {'name': 'palm', 'lower': [-.10, -.03, -.12], 'upper': [.10, .03, -.031]},
        {'name': 'leftfinger', 'lower': [-.012, -.01, -.044], 'upper': [0, .01, .009],
         'slide_per_half_opening': [-1, 0, 0]},
        {'name': 'rightfinger', 'lower': [0, -.01, -.044], 'upper': [.012, .01, .009],
         'slide_per_half_opening': [1, 0, 0]},
        {'name': 'leftfinger_pad', 'lower': [-.0075, -.008, -.0116], 'upper': [.0005, .008, .0044],
         'slide_per_half_opening': [-1, 0, 0]},
        {'name': 'rightfinger_pad', 'lower': [-.0005, -.008, -.0116], 'upper': [.0075, .008, .0044],
         'slide_per_half_opening': [1, 0, 0]}], 'references': [], 'collision_model': 'fixture_geometry'}


def test_contact_centre_uses_measured_flanks_instead_of_high_search_band_origin():
    rng = np.random.default_rng(112)
    points = np.concatenate([rng.uniform([x, -.018, .94], [x, .018, .95], (3000, 3))
                             for x in (-.02, .02)])
    contact, evidence = _opposition(points, np.array([0., 0., .956]), np.array([1., 0., 0.]))
    assert contact is not None
    assert .94 <= contact[2] <= .95
    assert abs(contact[0]) < 1e-8
    assert len(evidence['measured_contact_patch_centres_xyz']) == 2


def test_top_and_side_tcp_offsets_match_robot_pad_centre():
    from scipy.spatial.transform import Rotation

    cloud = cube_surface()
    _, rows = sample_grasps(cloud, cloud, 'box', [.1, 0, 1.2], 0., gripper_geometry())
    for approach in ('top', 'side_left'):
        row = next(r for r in rows if r['approach'] == approach and r.get('body_quat_xyzw'))
        site = Rotation.from_quat(row['body_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
        assert np.allclose(np.asarray(row['xyz']) + site @ row['pad_centre_site_m'],
                           row['public_pad_contact_centre_xyz'])


def test_mesh_bounds_detect_cabinet_and_preserve_opening_gap():
    geometry = gripper_geometry()
    points = np.array([[0, 0, 0], [0, 0, -.06], [.045, 0, -.02]])
    result = collision_counts(points, [0, 0, 0], np.eye(3), geometry, .08)
    assert result['palm'] == 1
    assert result['rightfinger'] == 1
    assert sum(result.values()) == 2


def test_actual_convex_mesh_excludes_empty_aabb_corner_but_keeps_collision():
    from scipy.spatial import ConvexHull

    vertices = np.array([[0., 0., 0.], [.1, 0., 0.], [0., .1, 0.], [0., 0., .1]])
    geometry = {'boxes': [{'name': 'hand', 'lower': [0., 0., 0.], 'upper': [.1, .1, .1],
                          'convex_halfspaces': ConvexHull(vertices).equations.tolist()}]}
    points = np.array([[.01, .01, .01], [.08, .08, .08], [.101, 0., 0.]])
    assert collision_counts(points, [0., 0., 0.], np.eye(3), geometry, .08)['hand'] == 2


def test_samples_multiple_yaws_and_top_and_side_entries_from_public_cloud():
    cloud = cube_surface()
    plan, records = sample_grasps(cloud, cloud, 'box', [.1, 0, 1.2], 0, gripper_geometry())
    assert plan is not None
    assert len({r['approach'] for r in records}) == 3
    assert len({tuple(r['closing_axis_xy']) for r in records}) == 4
    assert plan['measured_width_m'] < .072
    assert records[0]['rejected'] == []
    assert records[0]['normal_quality'][0] >= .65


def test_observed_obstacle_rejects_grasps_and_keeps_reasons():
    cloud = cube_surface()
    rng = np.random.default_rng(106)
    obstacle = rng.uniform([-.18, -.18, .95], [.18, .18, 1.15], (30000, 3))
    plan, records = sample_grasps(cloud, np.concatenate((cloud, obstacle)), 'box',
                                [.1, 0, 1.2], 0, gripper_geometry())
    assert plan is None
    assert all(r['rejected'] for r in records)
    assert any(r.get('collision') for r in records)


def test_site_closing_axis_matches_requested_public_yaw():
    angle = .4
    rotation = site_rotation(angle + np.pi/2)
    assert abs(np.dot(rotation[:2, 0], [np.cos(angle), np.sin(angle)])) > .999


def test_local_rim_opposition_excludes_far_side_outside_open_jaws():
    rng = np.random.default_rng(108)
    patches = []
    for x in (.054, .062, -.054, -.062):
        patch = rng.uniform([x, -.018, .91], [x, .018, .97], (3000, 3))
        patches.append(patch)
    contact, evidence = _opposition(np.concatenate(patches), np.array([.058, 0., .95]),
                                   np.array([1., 0., 0.]))
    assert contact is not None
    assert np.isclose(evidence['width_m'], .008)
    assert min(evidence['normal_quality']) > .99


def test_wide_object_does_not_gain_fake_flanks_from_local_crop():
    rng = np.random.default_rng(109)
    points = np.concatenate([rng.uniform([x, -.018, .91], [x, .018, .97], (3000, 3))
                             for x in (-.06, .06)])
    contact, evidence = _opposition(points, np.array([0., 0., .95]), np.array([1., 0., 0.]))
    assert contact is None
    assert evidence['reason'] == 'opposing_surfaces_not_measured'


def test_top_face_density_does_not_erase_coherent_opposing_side_patches():
    rng = np.random.default_rng(111)
    top = rng.uniform([-.024, -.018, .95], [.024, .018, .95], (4000, 3))
    sides = [rng.uniform([x, -.018, .94], [x, .018, .955], (400, 3)) for x in (-.02, .02)]
    contact, evidence = _opposition(np.concatenate([top, *sides]), np.array([0., 0., .95]),
                                   np.array([1., 0., 0.]))
    assert contact is not None
    assert min(evidence['normal_patch_support_counts']) >= 4
    assert min(evidence['normal_quality']) > .85


def test_visible_cap_palm_collision_selects_another_depth_without_ignoring_collision():
    from robots.libero.v5_analytic_grasp import top_grasp

    cloud = cube_surface()
    cloud[:, 2] = .90 + (cloud[:, 2] - .90) * (5 / 3)
    geometry = gripper_geometry()
    geometry['boxes'][0]['upper'][2] = -.027
    # A compartment admits the top hand but blocks horizontal approaches.
    # This fixture therefore checks the depth repair, rather than letting
    # an otherwise valid side grasp make the higher-top assertion irrelevant.
    rng = np.random.default_rng(110)
    walls = []
    for axis in (0, 1):
        for sign in (-1, 1):
            wall = rng.uniform([-.13, -.13, .88], [.13, .13, 1.1], (8000, 3))
            wall[:, axis] = sign * .13
            walls.append(wall)
    baseline = top_grasp(cloud, 'bottle', [.1, 0, 1.2], 0.)
    plan, rows = sample_grasps(cloud, np.concatenate([cloud, *walls]), 'bottle',
                               [.1, 0, 1.2], 0., geometry)
    assert plan is not None
    assert plan['xyz'][2] > baseline['xyz'][2]
    assert any(row.get('collision') and any(hit.get('target', {}).get('palm', 0)
               for hit in row['collision']) for row in rows)
    assert not rows[0]['rejected']


def test_side_grasp_fingers_are_horizontal_and_close_across_object():
    from scipy.spatial.transform import Rotation
    cloud = cube_surface()
    _, rows = sample_grasps(cloud, cloud, 'box', [.1, 0, 1.2], 0, gripper_geometry())
    side = next(r for r in rows if r['approach'] == 'side_left' and r.get('body_quat_xyzw'))
    site = (Rotation.from_quat(side['body_quat_xyzw']).as_matrix()
            @ Rotation.from_euler('z', -np.pi/2).as_matrix())
    assert abs(site[2, 2]) < 1e-8
    assert np.dot(site[:2, 0], side['closing_axis_xy']) > .999
    approach = np.asarray(side['xyz']) - side['approach_xyz']
    assert np.dot(site[:, 2], approach / np.linalg.norm(approach)) > .999
    assert np.isclose(np.linalg.det(side_site_rotation([1, 0, 0], [0, 1, 0])), 1)


def test_full_pose_servo_uses_public_orientation_feedback_and_stops():
    from scipy.spatial.transform import Rotation

    class Env:
        terminated = truncated = False

        def raw_obs(self):
            return {'robot0_eef_quat': policy.rotation.as_quat()}

    class Policy:
        env = Env()
        _last_obs_eef_pos = np.array([0., 0., 1.1])
        rotation = Rotation.identity()

        def _step_env(self, action):
            self._last_obs_eef_pos += action[:3] * .05
            self.rotation = Rotation.from_rotvec(action[3:6] * .50) * self.rotation

    policy = Policy()
    desired = Rotation.from_matrix(side_site_rotation([1, 0, 0], [0, 1, 0]))
    result = servo_grasp_pose(policy, [.04, -.03, 1.05], desired.as_quat(), trace_steps=True)
    assert result['actions_used'] > 0
    assert result['actions_used'] < 150
    assert result['final_dist_m'] < .008
    assert result['final_orientation_err_rad'] < .05
    assert result['trajectory']


def test_equivalent_side_flip_is_collision_checked_and_uses_measured_wrist_motion():
    from scipy.spatial.transform import Rotation

    cloud = cube_surface()
    desired = side_site_rotation([-1., 0., 0.], [0., 1., 0.])
    quat = Rotation.from_matrix(desired @ Rotation.from_euler('z', np.pi/2).as_matrix()).as_quat()
    _, rows = sample_grasps(cloud, cloud, 'box', [.1, 0, 1.2], 0., gripper_geometry(),
                            current_body_quat_xyzw=quat)
    accepted = {row['id']: row for row in rows if not row['rejected']}
    pairs = [(row, accepted[row['id'] + '_flip']) for row in accepted.values()
             if not row['parallel_jaw_flip'] and row['id'] + '_flip' in accepted]
    assert pairs
    assert any(flip['orientation_change_rad'] < row['orientation_change_rad']
               and flip['score'] > row['score'] for row, flip in pairs)
    assert all(flip['robot_geometry'] == row['robot_geometry'] for row, flip in pairs)
