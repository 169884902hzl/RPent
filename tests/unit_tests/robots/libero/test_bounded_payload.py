# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import numpy as np
import pytest


@pytest.mark.parametrize('obstacle', ['none', 'depth_jump', 'static'])
def test_current_pixels_beyond_old_extent_can_seed_same_surface_without_owning_obstacles(obstacle):
    from robots.libero.bounded_payload import complete_moving_boundary

    y, x = np.mgrid[:5, :6]
    world = np.stack([.1+x*.004, .1+y*.001, np.full(x.shape, .9)], axis=-1)
    mask = (x <= 2) | (x == 4)
    if obstacle == 'depth_jump':
        world[x == 3, 2] += .02
    stationary = world[x == 3] if obstacle == 'static' else np.array([[10., 10., 10.]])
    completed, evidence = complete_moving_boundary(world, mask, world[mask], stationary,
        surface_extent=[[.1, .1, .9], [.108, .104, .9]])
    assert completed[x == 3].all() if obstacle == 'none' else not completed[x == 3].any()
    assert not completed[x == 5].any()
    assert evidence['max_extrapolation_error_m'] == .001
from scipy.spatial.transform import Rotation

from robots.libero.bounded_payload import (
    _surface_registration,
    complete_moving_boundary,
    complete_spatial_payload_component,
    contact_axis_registration,
    contact_normal_registration,
    moving_payload_pixels,
    stationary_surface_registration,
)


def test_raw_spatial_edges_do_not_lose_a_connection_at_a_voxel_boundary():
    points = np.array([[0., 0., 1.], [.00099, 0., 1.], [.0037, 0., 1.],
                       [.0064, 0., 1.], [.012, 0., 1.], [np.nan, 0., 1.]])
    lower, upper = [-.001, -.01, .99], [.01, .01, 1.01]
    member, evidence = complete_spatial_payload_component(points, points[:1], [], lower, upper)
    assert member.tolist() == [True, True, True, True, False, False]
    assert evidence['private_pose_used'] is False
    # A pre-lift static point cannot bridge to the other component.
    member, _ = complete_spatial_payload_component(points, points[:1], [[.005, 0., 1.]], lower, upper)
    assert member.tolist() == [True, True, False, False, False, False]
    # A nearby unowned pixel is not an exact identity seed.
    member, _ = complete_spatial_payload_component(points, [[0., .0001, 1.]], [], lower, upper)
    assert not member.any()


def test_spatial_membership_is_union_of_seeded_components_with_unseeded_bridges():
    points = np.array([[0., 0., 1.], [0., 0., 1.], [.002, 0., 1.], [.004, 0., 1.],
                       [.1, 0., 1.], [.102, 0., 1.], [.2, 0., 1.], [.202, 0., 1.]])
    member, evidence = complete_spatial_payload_component(points, points[[0, 4]], [],
        [-1., -1., 0.], [1., 1., 2.])
    assert member.tolist() == [True]*6+[False, False]
    assert evidence['seed_pixels'] == 3  # Both duplicate raw pixels are seeds.
    assert evidence['exact_edges'] == 6


def test_all_seeded_spatial_pixels_retain_original_edge_count():
    points = np.zeros((1000, 3))
    member, evidence = complete_spatial_payload_component(points, points, [], [-1.]*3, [1.]*3)
    assert member.all()
    assert evidence['exact_edges'] == 499500
    assert evidence['seed_pixels'] == evidence['member_pixels'] == 1000


def test_contact_axis_fit_tracks_depth_not_segment_centres():
    surface = np.random.default_rng(97).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    for shift in (0., .02, -.02):
        measured = np.r_[surface+[0., shift, 0.], [[3., 3., 3.]]]
        fit = contact_axis_registration(surface, measured, 1, .02)
        assert fit['accepted'] and fit['private_pose_used'] is False
        assert abs(fit['translation_m'][1]-shift) <= .001
        assert fit['compatible_axis_interval_m'][0] <= shift <= fit['compatible_axis_interval_m'][1]
        low, high = fit['compatible_axis_interval_m']
        assert (low > .005) if shift > 0 else (high < -.005) if shift < 0 else (low > -.005 and high < .005)


def test_contact_axis_fit_retains_planar_ambiguity_and_missing_data():
    x, y = np.mgrid[-30:31, -30:31]
    plane = np.c_[x.ravel()*.001, y.ravel()*.001, np.zeros(x.size)]
    # The entire reference remains inside a larger, indistinguishable plane.
    fit = contact_axis_registration(plane[abs(plane[:, 1]) < .01], plane, 1, .02)
    assert fit['accepted']
    assert fit['compatible_axis_interval_m'][0] < -.005
    assert fit['compatible_axis_interval_m'][1] > .005
    for reference, current in ((plane[:10], plane), (plane, plane+[1., 0., 0.])):
        assert not contact_axis_registration(reference, current, 1, .02)['accepted']


def test_stationary_anchor_uses_shared_depth_instead_of_partial_surface_centre():
    source = np.random.default_rng(97).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    partial = source[source[:, 0] > .01]
    assert np.linalg.norm(np.median(partial, axis=0)-np.median(source, axis=0)) > .01
    fit = stationary_surface_registration(source, source, partial)
    assert fit['accepted'] and fit['private_pose_used'] is False
    assert fit['compatible_displacement_bound_m'] <= .01


def test_stationary_anchor_rejects_motion_ambiguity_and_missing_identity():
    source = np.random.default_rng(97).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    moved = source+[.02, 0., 0.]
    assert not stationary_surface_registration(source, moved, moved)['accepted']
    # A stationary neighbouring surface cannot establish the moved identity.
    assert not stationary_surface_registration(source, source, moved+[1., 0., 0.])['accepted']
    x, y = np.mgrid[-40:41, -40:41]
    plane = np.c_[x.ravel()*.001, y.ravel()*.001, np.zeros(x.size)]
    patch = plane[(abs(plane[:, 0]) < .01) & (abs(plane[:, 1]) < .01)]
    assert not stationary_surface_registration(patch, plane, patch)['accepted']
    assert not stationary_surface_registration(source[:10], source, source)['accepted']


def test_parallel_registration_preserves_all_measurements_and_verdicts():
    source = np.random.default_rng(97).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    partial = source[source[:, 0] > .01]
    for scene, instance in ((source, partial), (source+[.02, 0., 0.], source+[.02, 0., 0.])):
        serial = stationary_surface_registration(source, scene, instance)
        parallel = stationary_surface_registration(source, scene, instance, query_workers=4)
        assert parallel == serial
    for shift in (0., .02, -.02):
        scene = source+[0., shift, 0.]
        assert contact_axis_registration(source, scene, 1, .02, query_workers=4) == (
            contact_axis_registration(source, scene, 1, .02))


def test_capped_registration_queries_match_uncapped_measurements(monkeypatch):
    from robots.libero import bounded_payload
    tree_type = bounded_payload.cKDTree
    source = np.random.default_rng(98).uniform([-.02, -.015, -.01], [.02, .015, .01], (900, 3))
    scenes = [source + [0., shift, 0.] for shift in (0., .008, .02, .08)]
    capped = [contact_axis_registration(source, scene, 1, .02) for scene in scenes]

    class UncappedTree:
        def __init__(self, points):
            self.tree = tree_type(points)

        def query(self, points, **kwargs):
            kwargs.pop('distance_upper_bound', None)
            return self.tree.query(points, **kwargs)

    monkeypatch.setattr(bounded_payload, 'cKDTree', UncappedTree)
    assert capped == [contact_axis_registration(source, scene, 1, .02) for scene in scenes]


def test_contact_fit_corrects_normal_compliance_without_tangent_drift():
    x, z = np.mgrid[:20, :12]
    surface = np.stack([x.ravel()*.001, np.zeros(x.size), z.ravel()*.001], axis=-1)
    measured = surface+[0., .0014, 0.]
    # A separate nearby sheet does not determine the normal correction.
    measured = np.r_[measured, surface+[0., .012, 0.]]
    corrected, evidence = contact_normal_registration(surface, measured, [0., 1., 0.])
    assert evidence['accepted'] and evidence['private_pose_used'] is False
    np.testing.assert_allclose(corrected[:, [0, 2]], surface[:, [0, 2]])
    np.testing.assert_allclose(corrected[:, 1], .0014, atol=1e-6)
    assert evidence['rotation_rad'] == 0.
    assert evidence['median_residual_after_m'] < .000001


def test_contact_fit_keeps_missing_disjoint_and_out_of_range_surfaces_unmodified():
    x, z = np.mgrid[:20, :12]
    surface = np.stack([x.ravel()*.001, np.zeros(x.size), z.ravel()*.001], axis=-1)
    for measured, normal in ((surface[:10], [0., 1., 0.]),
                             (surface+[0., .020, 0.], [0., 1., 0.]),
                             (surface+[.1, 0., 0.], [0., 1., 0.]),
                             (surface, [0., 1., 0.]),
                             (surface, [0., 0., 0.])):
        corrected, evidence = contact_normal_registration(surface, measured, normal)
        assert not evidence['accepted']
        np.testing.assert_array_equal(corrected, surface)


def test_current_depth_component_recovers_edge_beyond_transport_extent_but_keeps_static_surface():
    y, x = np.mgrid[:8, :8]
    world = np.stack([x*.0025, y*.0025, np.full(x.shape, .1)], axis=-1)
    mask = (x < 5) & (y < 5)
    mask[4, 4] = False
    extent = [[-.001, -.001, .099], [.0085, .0085, .101]]
    complete, evidence = complete_moving_boundary(world, mask, world[mask],
        world[x >= 7], surface_extent=extent)
    assert complete[4, 4]
    assert complete[5, 5]
    assert not complete[:, 6:].any()
    assert evidence['depth_connected_current_surface_pixels'] > 0
    for modified, static in ((world, [world[4, 4]]),
                             (world+np.where((x == 4) & (y == 4), .01, 0.)[..., None]
                              * [0., 0., 1.], [[10., 10., 10.]])):
        blocked, _ = complete_moving_boundary(modified, mask, modified[mask], static,
            surface_extent=extent)
        assert not blocked[4, 4]


def test_depth_connected_rim_crosses_colour_but_keeps_static_and_depth_edges():
    y, x = np.mgrid[:8, :12]
    world = np.stack([x*.001, y*.001, .1+.0015*(x % 2)], axis=-1)
    world[:, 8:, 2] += .008
    image = np.full(world.shape, 30, dtype=np.uint8)
    image[:, 3:] = 210  # A painted rim belongs to the same measured surface.
    image[:, 8:] = 30  # Separate background supplies neither appearance nor depth continuity.
    mask = x < 3
    complete, evidence = complete_moving_boundary(world, mask, world[mask],
        world[y == 7], surface_extent=[[-.001, -.001, .09], [.02, .02, .12]], rgb=image)
    assert complete[2, 6]
    assert not complete[2, 8:].any()
    assert not complete[7].any()
    assert evidence['depth_connected_current_surface_pixels'] > 0


def test_depth_connected_completion_cannot_use_filtered_robot_pixels_as_a_bridge():
    y, x = np.mgrid[:8, :12]
    world = np.stack([x*.001, y*.001, np.full(x.shape, .1)], axis=-1)
    mask = x < 3
    world[:, 4:7] = np.nan  # Public self-filter removes this part of the hand.
    complete, _ = complete_moving_boundary(world, mask, world[mask],
        [[10., 10., 10.]], surface_extent=[[-.001, -.001, .09], [.02, .02, .12]],
        rgb=np.full(world.shape, 30, dtype=np.uint8))
    assert complete[:, 3].all()
    assert not complete[:, 4:].any()


def test_new_depth_members_seed_curved_boundary_completion_before_stopping():
    world = np.full((6, 3, 3), np.nan)
    world[:, 1] = np.c_[[0., .0005, .0025, .0064, .0105, .05], np.zeros(6), np.ones(6)]
    mask = np.zeros((6, 3), bool)
    mask[:2, 1] = True
    image = np.full(world.shape, 30, dtype=np.uint8)
    image[0] = 210
    complete, evidence = complete_moving_boundary(world, mask, world[mask],
        [world[4, 1]], surface_extent=[[-.001, -.01, .99], [.02, .01, 1.01]], rgb=image)
    # Row 2 needs depth connectivity across the colour change. Only then
    # do rows 1 and 2 jointly support the curved edge at row 3 (>3mm away).
    assert complete[2, 1] and complete[3, 1]
    assert not complete[4:, 1].any()  # Static surface and separate background.
    assert evidence['depth_connected_current_surface_pixels'] > 0


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


def test_appearance_completion_converges_but_does_not_cross_a_depth_jump():
    y, x = np.mgrid[:6, :7]
    z = .04+.006*np.maximum(x-2, 0)**2
    world = np.stack([x*.004, y*.004, z], axis=-1)
    mask = x < 3
    complete, evidence = complete_moving_boundary(world, mask, world[mask],
        [[10., 10., 10.]], surface_extent=[[-.001, -.001, .03], [.03, .03, .11]],
        rgb=np.full(world.shape, 30, dtype=np.uint8))
    assert complete[:, 4].all()  # Requires a second appearance-supported ring.
    assert not complete[:, 5:].any()  # 3cm depth jump exceeds measured support.
    assert len(evidence['appearance_boundary']['added_pixels_per_round']) >= 2


def test_current_semantic_silhouette_needs_rgb_depth_support_beyond_motion_extent():
    y, x = np.mgrid[:8, :7]
    world = np.stack([x*.004, y*.004, np.full(x.shape, .04)], axis=-1)
    mask = x < 3
    # Curved edge lies outside a transported/cleaned surface's extent.
    world[:, 3, 2] = .02
    world[:, 4:, 2] = -.08
    image = np.full(world.shape, 30, dtype=np.uint8)
    image[1, 3] = 120  # A different appearance cannot inherit membership.
    world[6, 3, 2] = .08  # Neither can a separate depth sheet.
    semantic = x <= 4  # SAM also bleeds into the depth background.
    static = [world[5, 3]]
    extent = [[-.001, -.001, .03], [.03, .04, .05]]
    old, _ = complete_moving_boundary(world, mask, world[mask], static,
        surface_extent=extent, rgb=image)
    assert not old[:, 3:].any()
    complete, evidence = complete_moving_boundary(world, mask, world[mask], static,
        surface_extent=extent, rgb=image, semantic_mask=semantic)
    assert complete[3, 3]
    assert not complete[1, 3]  # Appearance conflict.
    assert not complete[5, 3]  # Static scene veto.
    assert not complete[6, 3]  # Unsupported depth.
    assert not complete[:, 4:].any()  # Background despite semantic inclusion.
    assert evidence['appearance_boundary']['current_semantic_edge_pixels_outside_predicted_extent'] > 0
    assert len(evidence['appearance_boundary']['added_pixels_per_round']) < 5


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


def test_measured_surface_completion_converges_without_claiming_known_static_pixels():
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


def test_moving_extent_retains_current_measured_surface_after_partial_view_change():
    old = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    ref = {'target': [[0., 0., 0.]], 'scene': [[10., 10., 10.]],
           'robot': old, 'capture_step': 2}
    current = {**old, 'eef_xyz_m': [0., 0., .1]}
    matched, evidence = moving_payload_pixels([[0., 0., .09]], ref, current,
        current_target=[[0., 0., .09]])
    assert not matched.any()  # Existing 4mm rigid association is unchanged.
    np.testing.assert_allclose(evidence['measured_surface_extent_m'][0], [-.004, -.004, .086])
    np.testing.assert_allclose(evidence['measured_surface_extent_m'][1], [.004, .004, .104])


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


def test_curved_partial_view_validates_the_final_fit_instead_of_an_intermediate_iterate():
    # Original-task public RGB-D, job9026_16, row2, deterministically sampled
    # every 128 points. Its second ICP proposal exceeds 0.1 rad; the final fit
    # returns inside the original rotation and 15 mm displacement limits.
    with np.load(Path(__file__).parent/'fixtures/public_curved_payload_fit.npz') as capture:
        source, measured = capture['predicted'], capture['current']
    corrected, fit = _surface_registration(source, measured)
    assert fit['accepted']
    assert fit['rotation_rad'] <= fit['max_rotation_rad'] == .1
    assert fit['maximum_surface_displacement_m'] <= fit['max_surface_displacement_m'] == .015
    assert fit['median_residual_after_m'] < fit['median_residual_before_m']
    assert np.max(np.linalg.norm(corrected-source, axis=1)) <= .015


def test_precontact_reciprocal_fit_does_not_rotate_toward_an_occluded_silhouette():
    # Public RGB-D from original can init2/5 before and after finger contact.
    # Occluded reference points attracted by the remaining silhouette made
    # the one-sided fit exceed its rotation bound. These points are sampled
    # every 32 rows; no private pose or correspondence labels are stored.
    with np.load(Path(__file__).parent/'fixtures/public_precontact_occlusion_fit.npz') as capture:
        for case in (22, 25):
            source, measured = capture[f'can{case}_reference'], capture[f'can{case}_current']
            corrected, fit = _surface_registration(source, measured, reciprocal=True)
            assert fit['accepted']
            assert fit['correspondences'] == 'mutual_nearest_surface_pixels'
            assert fit['reciprocal_pairs'] >= 40
            assert fit['rotation_rad'] <= fit['max_rotation_rad'] == .1
            assert np.max(np.linalg.norm(corrected-source, axis=1)) <= .015
            assert fit['median_residual_after_m'] < fit['median_residual_before_m']


def test_static_destination_pixels_cannot_remain_in_the_initial_payload_mask():
    y, x = np.mgrid[:8, :12]
    world = np.stack([x*.002, y*.002, np.ones_like(x)], axis=-1)
    mask = np.ones(x.shape, bool)  # Semantic mask includes a neighbouring rim.
    complete, evidence = complete_moving_boundary(world, mask, world[x < 4],
        world[x >= 8], surface_extent=[[-.001, -.001, .999], [.03, .02, 1.001]])
    assert complete[:, :4].all()
    assert not complete[:, 8:].any()
    assert evidence['initial_mask_stationary_pixels_retained'] > 0


def test_rejected_registration_does_not_claim_the_old_predicted_surface():
    old = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    patch = np.array([[x, y, 0.] for x in np.linspace(-.02, .02, 15)
                      for y in np.linspace(-.02, .02, 15)])
    current = {**old, 'eef_xyz_m': [0., 0., .1]}
    visible = patch+[0., 0., .13]  # Measured compliance exceeds the allowed fit.
    reference = {'robot': old, 'target': patch, 'scene': [[10., 10., 10.]], 'capture_step': 1}
    owned, evidence = moving_payload_pixels(patch+[0., 0., .1], reference, current,
                                           current_target=visible)
    assert not owned.any()
    assert evidence['temporal_prediction_rejected']
    assert evidence['measured_surface_extent_m'][0][2] > .12


def test_partial_view_preserves_independently_co_moving_pixels_but_not_static_neighbour():
    old = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    patch = np.array([[x, y, 0.] for x in np.linspace(-.04, .04, 41)
                      for y in np.linspace(-.02, .02, 21)])
    current = {**old, 'eef_xyz_m': [0., 0., .1]}
    predicted = patch+[0., 0., .1]
    visible = predicted[predicted[:, 0] < -.025]
    neighbour = predicted[-1]+[0., 0., .001]
    reference = {'robot': old, 'target': patch, 'scene': [neighbour], 'capture_step': 1}
    points = np.array([predicted[len(predicted)//2], neighbour, [.08, 0., .1]])
    owned, evidence = moving_payload_pixels(points, reference, current, current_target=visible)
    assert evidence['surface_registration']['reason'] == 'surface_overlap_insufficient'
    assert evidence['partial_view_support']['rigid_prediction_retained']
    assert owned.tolist() == [True, False, False]
    assert evidence['stationary_points_retained'] == 1


def test_rejected_global_fit_keeps_only_independently_measured_semantic_fragments():
    old = {'eef_xyz_m': [0., 0., 0.], 'eef_quat_xyzw': [0., 0., 0., 1.]}
    patch = np.array([[x, y, 0.] for x in np.linspace(-.02, .02, 15)
                      for y in np.linspace(-.02, .02, 15)])
    current = {**old, 'eef_xyz_m': [0., 0., .1]}
    predicted = patch+[0., 0., .1]
    # Most current pixels contradict rigid motion. A small clean patch
    # supports it, and the current raw semantic mask contains two fragments.
    visible = np.vstack([patch+[0., 0., .13], predicted[:50]])
    fragment, static = predicted[-1], predicted[0]
    unsegmented = predicted[-3]
    mismatched = predicted[-4]+[0., 0., .002]
    points = np.array([fragment, static, unsegmented, mismatched])
    semantic = points[[0, 1, 3]]
    reference = {'robot': old, 'target': patch, 'scene': [static], 'capture_step': 1}
    owned, evidence = moving_payload_pixels(points, reference, current,
        current_target=visible, current_semantic_target=semantic)
    assert evidence['temporal_prediction_rejected']
    assert not evidence['surface_registration']['accepted']
    assert owned.tolist() == [True, False, False, False]
    assert evidence['associated_points'] == 1
    assert evidence['stationary_points_retained'] == 1
    # The rejected transform must not extend current measurement bounds.
    np.testing.assert_allclose(evidence['measured_surface_extent_m'],
        [visible.min(0)-.004, visible.max(0)+.004])
    weak = np.vstack([patch+[0., 0., .13], predicted[:39]])
    owned, evidence = moving_payload_pixels(points, reference, current,
        current_target=weak, current_semantic_target=semantic)
    assert evidence['temporal_prediction_rejected'] and not owned.any()
    assert evidence['current_semantic_temporal_fragments']['clean_supported_points'] == 39
