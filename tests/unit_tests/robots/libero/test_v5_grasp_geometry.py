import numpy as np

from robots.libero.v5_grasp_geometry import (
    clean_object_mask,
    depth_components,
    measure_pan_handle,
)


def test_contact_continuation_crosses_more_than_three_pixels_but_keeps_prior_extent():
    from robots.libero.v5_grasp_geometry import complete_contact_surface

    y, x = np.mgrid[:8, :50]
    world = np.stack([x*.0005, y*.0005, np.ones_like(x)], axis=-1)
    prior = np.vstack([world[x < 4], [.020, .0035, 1.]])
    complete, evidence = complete_contact_surface(world, prior)
    assert complete[:, 30].all()  # A previously omitted continuous handle side.
    assert not complete[:, 43:].any()  # Outside the previous contact extent.
    assert evidence['added_pixels'] > 0
    assert evidence['private_pose_used'] is False
    # A second surface inside that extent is still not a contact member.
    world[:, 18:, 2] += .002
    complete, _ = complete_contact_surface(world, prior)
    assert not complete[:, 18:].any()


def test_current_contact_boundary_remeasures_handle_edge_but_keeps_a_depth_jump():
    from robots.libero.v5_grasp_geometry import complete_contact_surface

    y, x = np.mgrid[:8, :20]
    world = np.stack([x*.001, y*.001, np.ones_like(x)], axis=-1)
    world[:, 12:, 2] += .006
    prior = world[x < 4]
    cached, _ = complete_contact_surface(world, prior)
    assert not cached[:, 7].any()
    current, evidence = complete_contact_surface(world, prior, current_boundary=True)
    assert current[:, 10].all()
    assert not current[:, 12:].any()
    assert evidence['private_pose_used'] is False


def test_planar_boundary_keeps_offset_surface_and_only_completes_one_ring():
    from robots.libero.v5_grasp_geometry import complete_planar_boundary

    y, x = np.mgrid[:12, :16]
    world = np.stack((x*.0008, y*.0008, np.full(x.shape, .95)), axis=-1)
    mask = (x >= 4) & (x < 8)
    completed, _ = complete_planar_boundary(world, mask)
    assert completed[:, 8].all()
    assert not completed[:, 9:].any()
    world[:, 8:, 2] += .002
    assert not complete_planar_boundary(world, mask)[0][:, 8:].any()


def test_crossview_boundary_needs_identity_depth_and_adjacent_surface():
    from robots.libero.v5_grasp_geometry import complete_crossview_boundary

    y, x = np.mgrid[:8, :12]
    world = np.stack((x*.001, y*.001, np.ones(x.shape)), axis=-1)
    mask = (x >= 3) & (x < 6)
    other_mask = (x >= 3) & (x < 8)
    metadata = {'width': 12, 'height': 8,
                'intrinsic_K': [[1000., 0., 0.], [0., 1000., 0.], [0., 0., 1.]],
                'extrinsic_cam2world': np.eye(4).tolist()}
    completed, detail = complete_crossview_boundary(world, mask, world, other_mask, metadata)
    assert completed[:, 6].all()
    assert completed[:, 7].all()  # Each pixel has independent other-view support.
    assert not completed[:, 8:].any()
    assert detail['added_pixels'] == 16
    occluder = world.copy()
    occluder[:, 6, 2] -= .01
    assert not complete_crossview_boundary(world, mask, occluder, other_mask, metadata)[0][:, 6].any()
    missing_identity = other_mask.copy()
    missing_identity[:, 6] = False
    assert not complete_crossview_boundary(world, mask, world, missing_identity, metadata)[0][:, 6].any()


def test_crossview_grazing_surface_uses_complete_measured_plane_patch():
    from robots.libero.v5_grasp_geometry import complete_crossview_boundary

    y, x = np.mgrid[:10, :12]
    # A calibrated plane with 7 mm between columns, sampled at half pixels
    # in the other camera. Nearest-point distance exceeds the 3 mm gate.
    other = np.stack((x*.007, y*.001, np.ones(x.shape)), axis=-1)
    world = other.copy()
    world[..., 0] += .0035
    world[:2] = other[:2]  # Shared identity seeds in every source column.
    mask, other_mask = (x < 5) | (y < 2), x < 10
    metadata = {'width': 12, 'height': 10,
        'intrinsic_K': [[1/.007, 0., 0.], [0., 1000., 0.], [0., 0., 1.]],
        'extrinsic_cam2world': np.eye(4).tolist()}
    completed, detail = complete_crossview_boundary(world, mask, other, other_mask, metadata)
    assert completed[4, 6] and detail['plane_supported_pixels'] > 0
    # The patch must contain neither an unlabelled pixel nor a depth edge.
    missing = other_mask.copy()
    missing[4, 6] = False
    assert not complete_crossview_boundary(world, mask, other, missing, metadata)[0][4, 6]
    offset = other.copy()
    offset[:, 6:, 2] += .01
    assert not complete_crossview_boundary(world, mask, offset, other_mask, metadata)[0][4, 6]
    displaced = world.copy()
    displaced[:, 6:, 2] += .002
    assert not complete_crossview_boundary(displaced, mask, other, other_mask, metadata)[0][4, 6]


def test_crossview_supported_patch_must_connect_without_a_depth_jump():
    from robots.libero.v5_grasp_geometry import complete_crossview_boundary

    y, x = np.mgrid[:8, :12]
    world = np.stack((x*.001, y*.001, np.ones(x.shape)), axis=-1)
    world[:, 7:, 2] += .02
    mask = (x >= 3) & (x < 6)
    metadata = {'width': 12, 'height': 8,
        'intrinsic_K': [[1000., 0., 0.], [0., 1000., 0.], [0., 0., 1.]],
        'extrinsic_cam2world': np.eye(4).tolist()}
    completed, _ = complete_crossview_boundary(world, mask, world, (x >= 3) & (x < 10), metadata)
    assert completed[:, 6].all()
    assert not completed[:, 7:].any()


def test_crossview_can_connect_a_self_occluded_surface_through_the_other_view():
    from robots.libero.v5_grasp_geometry import complete_crossview_boundary

    y, x = np.mgrid[:8, :22]
    z = 1.+np.maximum(0, x-3)*.001
    other = np.stack((x*.001*z, y*.001*z, z), axis=-1)
    world = other.copy()
    world[:, 6:, 2] = 1.4  # This view has an intervening depth discontinuity.
    world[:, 17] = other[:, 17]
    mask = (x >= 3) & (x < 6)
    metadata = {'width': 22, 'height': 8,
        'intrinsic_K': [[1000., 0., 0.], [0., 1000., 0.], [0., 0., 1.]],
        'extrinsic_cam2world': np.eye(4).tolist()}
    completed, evidence = complete_crossview_boundary(world, mask, other, (x >= 3) & (x < 19), metadata)
    assert completed[:, 17].all()
    assert evidence['shared_opposite_view_components']


def test_crossview_silhouette_rounding_can_use_adjacent_target_but_not_foreground():
    from robots.libero.v5_grasp_geometry import complete_crossview_boundary

    y, x = np.mgrid[:8, :12]
    world = np.stack((x*.001, y*.001, np.ones(x.shape)), axis=-1)
    mask = (x >= 3) & (x < 6)
    other = world.copy()
    other[:, 6:, 2] = 1.2  # Rounded projection lands behind the target edge.
    metadata = {'width': 12, 'height': 8, 'intrinsic_K': [[1000., 0., 0.],
        [0., 1000., 0.], [0., 0., 1.]], 'extrinsic_cam2world': np.eye(4).tolist()}
    completed, evidence = complete_crossview_boundary(world, mask, other, mask, metadata)
    assert completed[:, 6].all() and evidence['added_pixels'] == 8
    other[:, 6, 2] = .99  # A foreground occluder must remain an obstacle.
    assert not complete_crossview_boundary(world, mask, other, mask, metadata)[0][:, 6].any()


def test_boundary_completion_recovers_continuous_surface_but_keeps_depth_jump():
    from robots.libero.v5_grasp_geometry import complete_instance_boundary
    y,x = np.mgrid[:8,:16]
    world = np.stack((x*.0008,y*.0008,np.where(x<10,.95,.90)),axis=-1)
    mask = (x>=4)&(x<8)
    completed,evidence = complete_instance_boundary(world,mask)
    assert completed[:,8:10].all()
    assert not completed[:,10:].any()
    assert evidence['added_pixels_per_round'][0] > 0


def test_boundary_completion_does_not_carve_nearby_disconnected_points():
    from robots.libero.v5_grasp_geometry import complete_instance_boundary
    y,x = np.mgrid[:8,:16]
    world = np.stack((x*.0008,y*.0008,np.full(x.shape,.95)),axis=-1)
    world[:,8:,2] += .002
    mask = (x>=4)&(x<8)
    completed,_ = complete_instance_boundary(world,mask)
    assert not completed[:,8:].any()


def test_image_connected_masks_split_at_depth_jump():
    y, x = np.mgrid[:10, :20]
    world = np.stack((x * .002, y * .002, np.where(x < 10, .9, 1.1)), axis=-1)
    labels, sizes = depth_components(world, np.ones((10, 20), dtype=bool))
    assert sorted(sizes) == [100, 100]
    assert labels[0, 0] != labels[0, -1]


def test_stationary_target_does_not_switch_to_larger_distant_component():
    y, x = np.mgrid[:10, :30]
    world = np.stack((np.where(x < 10, x * .002, .2 + x * .002), y * .002,
                      np.full(x.shape, .92)), axis=-1)
    mask, detail = clean_object_mask(world, np.ones((10, 30), dtype=bool),
        prior_lower=[0, 0, .91], prior_upper=[.02, .02, .93])
    assert mask.sum() == 100
    assert not mask[:, 10:].any()
    assert any(c.get('rejected') == 'outside_stationary_measured_identity' for c in detail['components'])


def test_missing_stationary_source_produces_no_component():
    y, x = np.mgrid[:10, :10]
    world = np.stack((.3 + x * .002, y * .002, np.full(x.shape, .92)), axis=-1)
    mask, detail = clean_object_mask(world, np.ones((10, 10), dtype=bool),
        prior_lower=[0, 0, .91], prior_upper=[.02, .02, .93])
    assert not mask.any()
    assert detail['selected'] is None


def test_sparse_handle_is_found_without_requiring_ten_percent_of_all_points():
    rng = np.random.default_rng(92)
    angle = rng.uniform(0, 2*np.pi, 20000)
    radius = np.sqrt(rng.uniform(0, .01, 20000))
    body = np.c_[radius*np.cos(angle), radius*np.sin(angle), rng.uniform(.9, .915, len(angle))]
    handle = rng.uniform([.095, -.011, .905], [.23, .011, .915], (400, 3))
    measured, detail = measure_pan_handle(np.concatenate((body, handle)))
    assert measured is not None
    assert measured['centre_xy'][0] > .13
    assert detail['selected']['width_m'] < .03


def test_round_handleless_pan_does_not_invent_a_handle():
    rng = np.random.default_rng(93)
    angle = rng.uniform(0, 2*np.pi, 10000)
    radius = np.sqrt(rng.uniform(0, .01, 10000))
    body = np.c_[radius*np.cos(angle), radius*np.sin(angle), rng.uniform(.9, .915, len(angle))]
    assert measure_pan_handle(body)[0] is None


def test_oblique_box_camera_aims_at_measured_target_using_moving_mount():
    from scipy.spatial.transform import Rotation

    from robots.libero.v5_grasp_geometry import oblique_box_view
    from robots.libero.v5_state import Entity

    before = Entity('box', 'box', (0., 0., .93), (-.03, -.02, .9), (.03, .02, .96))
    body = Rotation.from_euler('xyz', [np.pi, .1, .3]).as_matrix()
    mount = Rotation.from_euler('y', .2).as_matrix()
    offset = np.array([.03, .02, -.04])
    eef = np.array([.01, 0., 1.2])
    extrinsic = np.eye(4)
    extrinsic[:3, :3] = body @ mount
    extrinsic[:3, 3] = eef + body @ offset
    views = [oblique_box_view(before, [0., 1.], eef, Rotation.from_matrix(body).as_quat(),
                             {'extrinsic_cam2world': extrinsic.tolist()}, sign) for sign in (-1, 1)]
    for view in views:
        desired = Rotation.from_quat(view['body_quat_xyzw']).as_matrix()
        camera = np.asarray(view['xyz']) + desired @ offset
        assert np.allclose(camera, view['camera_xyz'])
        ray = np.asarray(view['look_at_xyz']) - camera
        ray /= np.linalg.norm(ray)
        assert np.dot((desired @ mount)[:, 2], ray) > .999999
        assert view['private_pose_used'] is False
    assert views[0]['camera_xyz'][1] < 0 < views[1]['camera_xyz'][1]
