import numpy as np

from robots.libero.v5_grasp_public_tracking import translated_hint, pose_hint, matching_cloud
from robots.libero.v5_state import Entity


def test_robot_translation_hint_is_not_a_current_measurement():
    before = Entity('e1', 'bottle', (0., 0., .95), (-.02, -.02, .9), (.02, .02, 1.), source_step=5)
    hint = translated_hint(before, [0., 0., 1.], [0., 0., 1.1])
    assert np.allclose(hint.lower, [-.02, -.02, 1.])
    assert hint.source_step == before.source_step
    assert hint.geometry == 'public_robot_translation_hint_not_measurement'
    assert before.lower == (-.02, -.02, .9)


def test_distant_same_category_mask_cannot_replace_grasped_target():
    before = Entity('e1', 'bottle', (0., 0., .95), (-.02, -.02, .9), (.02, .02, 1.))
    hint = translated_hint(before, [0., 0., 1.], [0., 0., 1.1])
    rng = np.random.default_rng(3)
    near = rng.uniform([-.02, -.02, 1.], [.02, .02, 1.1], (30, 30, 3))
    mask = np.ones((30, 30), dtype=bool)
    assert matching_cloud(near, mask, hint) is not None
    far = near + [.2, .2, -.1]
    assert matching_cloud(far, mask, hint) is None


def test_wrist_rotation_updates_query_region_without_claiming_measurement():
    from scipy.spatial.transform import Rotation

    before = Entity('e1', 'bottle', (.05, 0., 1.), (.04, -.01, .95), (.06, .01, 1.05), source_step=7)
    hint = pose_hint(before, [0.,0.,1.], [0.,0.,1.1], [0.,0.,0.,1.],
                     Rotation.from_euler('z', 90, degrees=True).as_quat())
    assert np.allclose(hint.xyz, [0., .05, 1.1])
    assert np.allclose(hint.lower, [-.01, .04, 1.05])
    assert np.allclose(hint.upper, [.01, .06, 1.15])
    assert hint.source_step == 7 and hint.geometry == 'public_robot_pose_hint_not_measurement'
    cloud = np.random.default_rng(8).uniform([-.009,.041,1.055], [.009,.059,1.145], (30,30,3))
    assert matching_cloud(cloud, np.ones((30,30),dtype=bool), hint) is not None
    assert matching_cloud(cloud + [.3,0.,0.], np.ones((30,30),dtype=bool), hint) is None
    assert before.xyz == (.05,0.,1.)


def test_pose_hint_at_fixed_orientation_matches_existing_translation():
    before = Entity('e1', 'bottle', (0.,0.,.9), (-.02,-.02,.8), (.02,.02,1.))
    a = translated_hint(before, [0.,0.,1.], [.1,.2,1.1])
    b = pose_hint(before, [0.,0.,1.], [.1,.2,1.1], [1.,0.,0.,0.], [1.,0.,0.,0.])
    assert np.allclose(a.xyz,b.xyz) and np.allclose(a.lower,b.lower) and np.allclose(a.upper,b.upper)


def test_missing_measured_wrist_pose_cannot_be_replaced_by_identity_rotation():
    import pytest
    before = Entity('e1', 'bottle', (0.,0.,.9), (-.02,-.02,.8), (.02,.02,1.))
    with pytest.raises(ValueError):
        pose_hint(before, [0.,0.,1.], [0.,0.,1.1], None, [1.,0.,0.,0.])


def coupling_frames(*, object_motion=.04, robot_motion=.04, empty=False):
    frames = []
    for step, delta in ((1, 0.), (2, object_motion)):
        conditions = {'fresh_visible': True, 'measured_lower_lift': True,
            'near_measured_fingers': False, 'calibrated_nonempty_opening': not empty,
            'original_measured_support_clearance': True}
        measurement = {'id': 'e1', 'name': 'bottle', 'xyz': [0., 0., .2 + delta],
            'visible': True, 'src': 'perception', 'source_step': step}
        frames.append({'version': 'measured-grasp-independent-views/2-dev',
            'eef_xyz': [0., 0., .3 + (robot_motion if step == 2 else 0.)],
            'body_quat_xyzw': [1., 0., 0., 0.], 'previous_step': 0,
            'verified': False, 'per_view': {'agentview': {'measurement': measurement,
                'current_measurement': True, 'verified': False, 'conditions': conditions,
                'finger_geometry': {'mode': 'calibrated_finger_frame'}}}})
    return frames


def test_occluded_contact_needs_independent_measured_body_translation():
    import copy
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames()
    original = copy.deepcopy(frames)
    result = evaluate_tracked_coupling(*frames, .5)
    assert result['verified'] is True
    assert frames == original
    assert evaluate_tracked_coupling(*coupling_frames(object_motion=0.), .5)['verified'] is None
    assert evaluate_tracked_coupling(*coupling_frames(robot_motion=0.), .5)['verified'] is None


def test_tracking_coupling_cannot_override_empty_gripper_or_unlifted_body():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    assert evaluate_tracked_coupling(*coupling_frames(empty=True), .5)['verified'] is False
    frames = coupling_frames()
    frames[0]['per_view']['agentview']['conditions']['measured_lower_lift'] = False
    assert evaluate_tracked_coupling(*frames, .5)['verified'] is False


def test_visible_contact_volume_cannot_bypass_required_motion_evidence():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    def visible_frames(**kwargs):
        frames = coupling_frames(**kwargs)
        for frame in frames:
            frame.update(verified=True)
            view = frame['per_view']['agentview']
            view.update(verified=True)
            view['conditions']['near_measured_fingers'] = True
        return frames

    # The old positive volume can pass even when the visible object stays put.
    assert evaluate_tracked_coupling(*visible_frames(object_motion=0.), .5)['verified'] is True
    assert evaluate_tracked_coupling(*visible_frames(object_motion=0.), .5,
                                    require_coupled_motion=True)['verified'] is False
    assert evaluate_tracked_coupling(*visible_frames(robot_motion=.02), .5,
                                    require_coupled_motion=True)['verified'] is None
    assert evaluate_tracked_coupling(*visible_frames(), .5,
                                    require_coupled_motion=True)['verified'] is True


def test_required_motion_preserves_empty_gripper_failure_and_view_disagreement():
    import copy
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames()
    for frame in frames:
        frame['per_view']['wrist'] = copy.deepcopy(frame['per_view']['agentview'])
    frames[1]['per_view']['wrist']['measurement']['xyz'][2] -= .04
    result = evaluate_tracked_coupling(*frames, .5, require_coupled_motion=True)
    assert result['verified'] is None
    assert result['required_coupled_motion']['reason'] == 'fresh_views_disagree'
    assert evaluate_tracked_coupling(*coupling_frames(empty=True), .5,
                                    require_coupled_motion=True)['verified'] is False


def test_stale_or_changed_identity_cannot_supply_coupling():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames()
    frames[1]['per_view']['agentview']['measurement']['source_step'] = 1
    assert evaluate_tracked_coupling(*frames, .5)['verified'] is None
    frames = coupling_frames()
    frames[1]['per_view']['agentview']['measurement']['id'] = 'e2'
    assert evaluate_tracked_coupling(*frames, .5)['verified'] is None


def test_missing_rgbd_does_not_hide_measured_empty_closed_gripper():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames()
    for frame in frames:
        frame.update(per_view={}, verified=None, opening_m=.001)
    calibration = {'closed_empty_max_m': .0018488, 'tolerance_m': .0008536}
    actual = evaluate_tracked_coupling(*frames, .5, opening_calibration=calibration)
    assert actual['verified'] is False
    assert actual['empty_aperture_evidence']['empty_frame'] == [True, True]
    assert frames[0]['verified'] is None  # Raw measurements are preserved.


def test_nonempty_aperture_without_rgbd_remains_unknown():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames()
    for frame in frames:
        frame.update(per_view={}, verified=None, opening_m=.035)
    actual = evaluate_tracked_coupling(*frames, .5,
        opening_calibration={'closed_empty_max_m': .0018488, 'tolerance_m': .0008536})
    assert actual['verified'] is None


def test_stationary_requery_rejects_known_same_category_peers_even_when_occluded():
    from types import SimpleNamespace as NS
    from robots.libero.v5_grasp_public_tracking import stationary_source_is_unique

    before = Entity('e1', 'bottle', (0., 0., .8), (-.02, -.02, .7), (.02, .02, .9))
    peer = Entity('e2', 'bottle', (.3, 0., .8), (.28, -.02, .7), (.32, .02, .9), visible=False)
    scene = NS(entities={'e1': before})
    assert stationary_source_is_unique(scene, before)
    scene.entities['e2'] = peer
    assert not stationary_source_is_unique(scene, before)


def test_fresh_stationary_target_is_negative_lift_evidence_not_a_robot_motion_hint():
    from robots.libero.v5_grasp_public_tracking import evaluate_tracked_coupling

    frames = coupling_frames(object_motion=0.)
    for frame in frames:
        frame['per_view']['agentview']['conditions']['measured_lower_lift'] = False
    result = evaluate_tracked_coupling(*frames, .5,
        opening_calibration={'closed_empty_max_m': .0018488, 'tolerance_m': .0008536})
    assert result['verified'] is False
    assert not result['coupled_lift_evidence']['per_view']['agentview']['coupling_measured']


def test_public_pad_measurement_uses_signed_joint_positions_and_current_target_points():
    from robots.libero.v5_grasp_public_tracking import measure_finger_pad_regions

    frame = {'eef_xyz': [0., 0., 1.], 'body_quat_xyzw': [0., 0., 0., 1.],
             'opening_calibration_tolerance_m': .001,
             'per_view': {'wrist': {'current_measurement': True,
                                  'measurement': {'id': 'e1', 'source_step': 4}}}}
    geometry = {'xml': {'path': 'synthetic_robot.xml', 'sha256': 'fixture_only'},
                'rotation_body_to_site': np.eye(3).tolist(),
                'finger_pads': [{'neutral_centre_site_m': [0., 0., 0.],
                                 'joint_axis_site': [1., 0., 0.],
                                 'half_size_site_m': [.004, .008, .008], 'geom_name': name}
                                for name in ('left_pad', 'right_pad')]}
    cloud = {'wrist': {'src': 'perception', 'object_id': 'e1', 'source_step': 4,
                       'xyz_world': [[.016, 0., 1.], [-.006, 0., 1.]]}}
    result = measure_finger_pad_regions(frame, cloud, geometry, [.02, -.01])
    pads = result['per_view']['wrist']['pads']
    assert [p['centre_site_m'][0] for p in pads] == [.02, -.01]
    assert [p['points_within_measured_tolerance'] for p in pads] == [1, 1]
    assert result['positive_grasp_inferred'] is False
    assert result['private_pose_or_contact_used'] is False
    for field, value in [('src', 'sim_truth'), ('source_step', 3), ('object_id', 'e2')]:
        changed = {'wrist': {**cloud['wrist'], field: value}}
        rejected = measure_finger_pad_regions(frame, changed, geometry, [.02, -.01])
        assert rejected['per_view']['wrist']['pads'] == []


def test_rotated_pad_measurement_distinguishes_outer_finger_from_inner_pad():
    from scipy.spatial.transform import Rotation
    from robots.libero.v5_grasp_public_tracking import measure_finger_pad_regions

    rotation = Rotation.from_euler('z', 90, degrees=True)
    frame = {'eef_xyz': [0., 0., 1.], 'body_quat_xyzw': rotation.as_quat().tolist(),
             'opening_calibration_tolerance_m': .001,
             'per_view': {'agentview': {'current_measurement': True,
                                      'measurement': {'id': 'e1', 'source_step': 4}}}}
    geometry = {'xml': {'path': 'synthetic_robot.xml'},
                'rotation_body_to_site': np.eye(3).tolist(),
                'finger_pads': [{'neutral_centre_site_m': [0., 0., 0.],
                                 'joint_axis_site': [1., 0., 0.],
                                 'half_size_site_m': [.004, .008, .008], 'geom_name': name}
                                for name in ('left_pad', 'right_pad')]}
    points = rotation.apply([[.016, 0., 0.], [-.03, .03, .04]]) + [0., 0., 1.]
    cloud = {'agentview': {'src': 'perception', 'object_id': 'e1', 'source_step': 4,
                           'xyz_world': points.tolist()}}
    result = measure_finger_pad_regions(frame, cloud, geometry, [.02, -.01])
    pads = result['per_view']['agentview']['pads']
    assert pads[0]['points_within_measured_tolerance'] == 1
    assert pads[1]['points_within_measured_tolerance'] == 0
    assert pads[1]['target_surface_min_distance_m'] > .001


def test_outer_pad_face_cannot_count_as_measured_inward_face_contact():
    from robots.libero.v5_grasp_public_tracking import measure_finger_pad_regions

    frame = {'eef_xyz': [0., 0., 0.], 'body_quat_xyzw': [0., 0., 0., 1.],
             'opening_calibration_tolerance_m': .001,
             'per_view': {'agentview': {'current_measurement': True,
                                      'measurement': {'id': 'e1', 'source_step': 4}}}}
    geometry = {'xml': {'path': 'synthetic_robot.xml'},
                'rotation_body_to_site': np.eye(3).tolist(),
                'finger_pads': [{'neutral_centre_site_m': [0., 0., 0.],
                                 'joint_axis_site': [1., 0., 0.],
                                 'half_size_site_m': [.004, .008, .008], 'geom_name': name}
                                for name in ('left_pad', 'right_pad')]}
    cloud = {'agentview': {'src': 'perception', 'object_id': 'e1', 'source_step': 4,
                          'xyz_world': [[.024, 0., 0.], [.02, 0., 0.]]}}
    result = measure_finger_pad_regions(frame, cloud, geometry, [.02, -.02])
    left = result['per_view']['agentview']['pads'][0]
    assert left['target_surface_min_distance_m'] == 0.
    assert left['points_near_inward_face'] == 0
    assert left['target_surface_min_inward_face_distance_m'] > .001
    assert left['target_points_deep_inside_pad_box'] == 1
    assert left['inward_face_contact_inferred'] is False
    assert result['positive_grasp_inferred'] is False


def test_runtime_probe_reaches_the_required_public_translation(monkeypatch):
    import copy
    import itertools
    from types import SimpleNamespace as NS
    from robots.libero.v5_runtime import V5Executor

    positions = np.array([0., 0., .3])
    env = NS(terminated=False, truncated=False,
             raw_obs=lambda: {'robot0_eef_quat': np.array([1., 0., 0., 0.])})
    p = NS(env=env, _last_obs_eef_pos=positions)
    frames, sequence = coupling_frames(), itertools.count()

    def frame(before, support):
        index = next(sequence)
        measured = copy.deepcopy(frames[index])
        measured['eef_xyz'] = p._last_obs_eef_pos.tolist()
        measured['per_view']['agentview']['measurement']['xyz'] = [0., 0., positions[2] - .1]
        return measured

    def move(target, gripper, *, recoverable, tolerance_m):
        # The real servo may stop anywhere inside its accepted tolerance.
        positions[:] = target
        positions[2] -= tolerance_m
        return {'waypoint_reached': True}

    fake = NS(p=p, grasp_public_tracking_v1=True, grasp_required_coupling_v1=False,
              grasp_opposed_pad_window_v1=False,
              grasp_public_closing_xyz=positions.copy(),
              grasp_measurement_calibration=None, last_verification_measurements={},
              independent_grasp_frame=frame, _measure_grasp_pad_regions=lambda *args: None,
              move=move)
    monkeypatch.setattr('robots.libero.v5_grasp_public_tracking.refresh_grasp_target',
                        lambda *args: {'source': 'perception'})
    ticks = itertools.count()
    monkeypatch.setattr('robots.libero.v5_runtime.time.perf_counter', lambda: next(ticks) * .5)
    before = Entity('e1', 'bottle', (0., 0., .1), (-.02, -.02, .05), (.02, .02, .15))
    assert V5Executor.verify_independent_grasp(fake, before) is True
    evidence = fake.last_verification_measurements['independent_grasp']['coupled_lift_evidence']
    assert evidence['per_view']['agentview']['robot_translation_m'] >= .03


def public_hold_fixture():
    import copy
    frame = coupling_frames()[1]
    frames = [copy.deepcopy(frame) for _ in range(3)]
    for step, item in enumerate(frames, 2):
        item['per_view']['agentview']['measurement']['source_step'] = step
    proprioception = [{'used_sim_steps': step, 'opening_m': .03} for step in range(11)]
    return frames, proprioception, {'closed_empty_max_m': .0018, 'tolerance_m': .0009}


def test_public_hold_uses_physical_steps_and_cannot_count_inference_time():
    from robots.libero.v5_grasp_public_tracking import evaluate_public_hold_window

    frames, sensors, calibration = public_hold_fixture()
    assert evaluate_public_hold_window(frames, sensors, opening_calibration=calibration)['verified'] is True
    no_physics = [{**row, 'used_sim_steps': 0} for row in sensors]
    result = evaluate_public_hold_window(frames, no_physics, opening_calibration=calibration)
    assert result['verified'] is None and result['duration_s'] == 0


def test_public_hold_detects_intermittent_empty_aperture_and_body_slip():
    from robots.libero.v5_grasp_public_tracking import evaluate_public_hold_window

    frames, sensors, calibration = public_hold_fixture()
    sensors[4]['opening_m'] = .001
    assert evaluate_public_hold_window(frames, sensors, opening_calibration=calibration)['verified'] is False
    frames, sensors, calibration = public_hold_fixture()
    frames[1]['per_view']['agentview']['measurement']['xyz'][0] += .011
    assert evaluate_public_hold_window(frames, sensors, opening_calibration=calibration)['verified'] is False


def test_public_hold_preserves_missing_changed_and_private_measurements():
    import copy
    from robots.libero.v5_grasp_public_tracking import evaluate_public_hold_window

    frames, sensors, calibration = public_hold_fixture()
    for field, value in [('src', 'sim_truth'), ('source_step', 2), ('id', 'other')]:
        changed = copy.deepcopy(frames)
        changed[1]['per_view']['agentview']['measurement'][field] = value
        assert evaluate_public_hold_window(changed, sensors, opening_calibration=calibration)['verified'] is None
    assert evaluate_public_hold_window(frames[:2], sensors, opening_calibration=calibration)['verified'] is None


def test_public_hold_never_controls_a_terminal_environment():
    from types import SimpleNamespace as NS
    from robots.libero.v5_runtime import V5Executor

    def unexpected_control(*args):
        raise AssertionError('terminal environment must not receive controls')

    env = NS(terminated=True, truncated=False,
             raw_obs=lambda: {'robot0_gripper_qpos': np.array([.02, -.02]),
                              'robot0_eef_pos': np.zeros(3), 'robot0_eef_quat': np.array([0., 0., 0., 1.])},
             execution_budget=lambda: {'used_sim_steps': 100})
    fake = NS(p=NS(env=env, _step_env=unexpected_control),
              grasp_measurement_calibration={'opening_calibration': {'closed_empty_max_m': .0018, 'tolerance_m': .0009}})
    result = V5Executor.measure_public_grasp_hold(fake, None, None, {})
    assert result['verified'] is None and len(result['proprioception']) == 1
