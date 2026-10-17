import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_payload import (
    complete_moving_boundary,
    moving_payload_pixels,
)


def test_curved_rgbd_silhouette_keeps_static_neighbours_and_depth_background():
    y, x = np.mgrid[:6, :5]
    world = np.stack([x*.004, y*.004, np.full(x.shape, .04)], axis=-1)
    mask = x < 3
    world[:, 3, 2] = .02
    world[:, 4, 2] = 0.
    world[5, 3, 2] = .08
    image = np.full(world.shape, 30, dtype=np.uint8)
    complete, evidence = complete_moving_boundary(world, mask, world[mask],
        [world[4, 3]], surface_extent=[[-.001, -.001, .01], [.03, .03, .05]], rgb=image)
    assert complete[1, 3]  # Curved surface, 2cm from its adjacent foreground.
    assert not complete[4, 3]  # Same appearance, but measured static.
    assert not complete[:, 4].any()  # Background beyond the moving extent.
    assert not complete[5, 3]  # Separate depth surface beyond that extent.
    assert evidence['appearance_boundary']['added_pixels'] > 0


def test_temporal_edge_seed_extends_a_continuous_surface_but_keeps_static_neighbours():
    y, x = np.mgrid[:8, :10]
    world = np.stack([x*.0025, y*.0025, np.ones_like(x)], axis=-1)
    mask = x < 3
    moving = world[x == 3]
    static = world[x >= 8]
    complete, evidence = complete_moving_boundary(world, mask, moving, static)
    assert complete[:, 5].all()
    assert not complete[:, 8:].any()
    assert evidence['temporal_seed_pixels'] == 8
    assert evidence['stationary_points_retained'] > 0


def test_temporal_edge_continuation_keeps_a_depth_discontinuity():
    y, x = np.mgrid[:8, :10]
    world = np.stack([x*.001, y*.001, np.ones_like(x)], axis=-1)
    world[:, 5:, 2] += .02
    mask = x < 3
    complete, _ = complete_moving_boundary(world, mask, world[x == 3], [[10., 10., 10.]])
    assert complete[:, 4].all()
    assert not complete[:, 5:].any()
    unchanged, evidence = complete_moving_boundary(world, mask, [], [[10., 10., 10.]])
    np.testing.assert_array_equal(unchanged, mask)
    assert evidence['added_pixels'] == 0


def test_measured_surface_extent_allows_more_than_three_pixels_without_growing_outside_it():
    y, x = np.mgrid[:8, :30]
    world = np.stack([x*.001, y*.001, np.ones_like(x)], axis=-1)
    mask = x < 3
    extent = [[0., 0., .999], [.015, .007, 1.001]]
    complete, evidence = complete_moving_boundary(world, mask, world[x == 3],
        world[x >= 14], surface_extent=extent)
    assert complete[:, 9].all()
    assert not complete[:, 14:].any()
    assert len(evidence['added_pixels_per_round']) > 3
    assert evidence['stationary_points_retained'] > 0


def test_moving_grazing_surface_uses_measured_pixel_spacing_and_keeps_static_pixels():
    y, x = np.mgrid[:8, :10]
    # Foreshortening gives 10 mm per image pixel along the measured surface.
    # A fixed 3 mm neighbour gap misses a continuous omitted rim here.
    world = np.stack([x*.01, y*.002, 1.+x*.002], axis=-1)
    mask = x < 3
    static = world[x >= 6]
    complete, _ = complete_moving_boundary(world, mask, world[x == 3], static)
    assert complete[:, 5].all()
    assert not complete[:, 6:].any()
    # The same spacing cannot bridge a depth jump to a different surface.
    world[:, 5:, 2] += .025
    complete, _ = complete_moving_boundary(world, mask, world[x == 3], [[10., 10., 10.]])
    assert not complete[:, 5:].any()


def test_planar_recovery_seeds_further_tangent_completion_without_claiming_static_points():
    y, x = np.mgrid[:8, :12]
    positions = np.where(x < 3, x*.0008, .0016+(x-2)*.0025)
    world = np.stack([positions, y*.0008, np.ones_like(positions)], axis=-1)
    mask = x < 3
    # The change in pixel spacing needs plane support first; subsequent
    # omitted pixels agree with the newly measured tangent.
    complete, evidence = complete_moving_boundary(world, mask, world[x == 2],
        world[x >= 8], surface_extent=[[-.001, -.001, .999], [.03, .01, 1.001]])
    assert complete[:, 6].all()
    assert not complete[:, 8:].any()
    assert sum(evidence['planar_added_pixels_per_round']) > 0
    assert evidence['stationary_points_retained'] > 0
    # A nearby but different surface still cannot inherit the instance.
    world[:, 6:, 2] += .004
    complete, _ = complete_moving_boundary(world, mask, world[x == 2],
        [[10., 10., 10.]], surface_extent=[[-.001, -.001, .999], [.03, .01, 1.01]])
    assert not complete[:, 6:].any()


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


def test_measured_surface_refines_small_grip_shift_without_erasing_a_static_neighbour():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    target = np.array([[x, y, 0.] for x in np.linspace(-.02, .02, 20)
                       for y in np.linspace(-.02, .02, 20)])
    current = {**robot, 'eef_xyz_m': [0., 0., .1]}
    measured = target+[0., 0., .106]
    neighbour = [.005, .005, .106]
    ref = {'target': target, 'scene': np.vstack([target, neighbour]),
           'robot': robot, 'capture_step': 1}
    points = np.array([[0., 0., .106], neighbour, [.06, 0., .106]])
    unrefined, _ = moving_payload_pixels(points, ref, current)
    refined, evidence = moving_payload_pixels(points, ref, current, current_target=measured)
    assert unrefined.tolist() == [False, False, False]
    assert refined.tolist() == [True, False, False]
    fit = evidence['surface_registration']
    assert fit['accepted']
    np.testing.assert_allclose(fit['translation_m'], [0., 0., .006], atol=1e-12)
    assert evidence['stationary_points_retained'] == 1


def test_distant_current_instance_cannot_pull_the_payload_model_to_an_obstacle():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    target = np.array([[x, y, 0.] for x in np.linspace(-.02, .02, 20)
                       for y in np.linspace(-.02, .02, 20)])
    ref = {'target': target, 'scene': target, 'robot': robot, 'capture_step': 1}
    current = {**robot, 'eef_xyz_m': [0., 0., .1]}
    matched, evidence = moving_payload_pixels([[0., 0., .15]], ref, current, current_target=target+[0., 0., .15])
    assert not matched.any() and not evidence['surface_registration']['accepted']


def test_grip_tilt_recovers_moving_edge_but_keeps_stationary_neighbour():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    # The lower lip is missing from the current view, but the visible curved
    # surface constrains a small grip tilt. A translation alone cannot fit it.
    target = np.array([[x, y, .3*x*x+2*y*y] for x in np.linspace(-.06, .06, 40)
                       for y in np.linspace(-.04, .04, 40)])
    target = np.vstack([target, [.06, -.06, -.04]])
    rotation = Rotation.from_euler('x', .07).as_matrix()
    moved = target@rotation.T+[0., 0., .1]
    neighbour = moved[0]+[.001, 0., 0.]
    ref = {'target': target, 'scene': np.vstack([target, neighbour]),
           'robot': robot, 'capture_step': 3}
    current = {**robot, 'eef_xyz_m': [0., 0., .1]}
    points = np.vstack([moved[-1], neighbour])
    matched, evidence = moving_payload_pixels(points, ref, current, current_target=moved[:-1])
    assert matched.tolist() == [True, False]
    fit = evidence['surface_registration']
    assert fit['accepted'] and .05 < fit['rotation_rad'] < .1
    assert fit['maximum_surface_displacement_m'] <= .015
    assert evidence['stationary_points_retained'] == 1


def test_large_grip_rotation_cannot_relabel_a_nearby_surface():
    robot = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    target = np.array([[x, y, 0.] for x in np.linspace(-.04, .04, 30)
                       for y in np.linspace(-.04, .04, 30)])
    moved = target@Rotation.from_euler('x', .15).as_matrix().T+[0., 0., .1]
    ref = {'target': target, 'scene': target, 'robot': robot, 'capture_step': 1}
    current = {**robot, 'eef_xyz_m': [0., 0., .1]}
    matched, evidence = moving_payload_pixels([moved[-1]], ref, current, current_target=moved)
    assert not matched.any()
    assert not evidence['surface_registration']['accepted']
