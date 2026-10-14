from types import SimpleNamespace

import numpy as np
import pytest

from robots.libero.v5_analytic_grasp import top_grasp, execute_analytic_grasp, measured_side_route
from robots.libero.v5_state import Entity


def box_cloud(width=.035, length=.06, yaw=.7):
    rng = np.random.default_rng(5)
    points = rng.uniform([-.5*length, -.5*width, .9], [.5*length, .5*width, .96], (4000, 3))
    rotation = np.array([[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]])
    points[:, :2] = points[:, :2] @ rotation.T
    return points


def test_measured_cabinet_contact_replay_routes_outside_visible_furniture():
    cabinet = Entity('cab', 'cabinet', (.05, -.22, 1.08),
                     (-.109, -.341, .924), (.118, -.060, 1.127), source_step=4)
    plan = {'xyz': [-.142, -.025, .911], 'closing_axis_xy': [.36, -.93]}
    route = measured_side_route(plan, [cabinet], 'box', 1.185)
    above, low, contact = [p for _, p in route['waypoints']]
    assert above[2] >= cabinet.upper[2] + .15
    assert low[0] < cabinet.lower[0] - .10 or low[1] > cabinet.upper[1] + .10
    assert contact == plan['xyz']
    assert route['obstacles'][0]['source_step'] == 4
    assert route['private_pose_used'] is False
    assert route['terminal_clearance_verified'] is False
    entry = np.asarray(contact[:2]) - low[:2]
    assert np.dot(entry, plan['closing_axis_xy']) == pytest.approx(0., abs=1e-10)


def test_side_entry_does_not_push_with_an_open_finger_along_closure_axis():
    cabinet = Entity('cab', 'cabinet', (0, -.2, 1.1), (-.11, -.34, .92), (.12, -.06, 1.13))
    plan = {'xyz': [-.142, -.025, .911], 'closing_axis_xy': [0., 1.]}
    route = measured_side_route(plan, [cabinet], 'butter', 1.2)
    side = route['waypoints'][1][1]
    assert side[0] < cabinet.lower[0] - .10
    assert side[1] == plan['xyz'][1]
    assert route['entry_axis_basis'] == 'perpendicular_to_measured_gripper_closing_axis'


def test_no_side_route_for_cached_or_distant_furniture():
    distant = Entity('cab', 'cabinet', (.4, -.2, 1.08), (.3, -.3, .92), (.5, -.1, 1.13))
    cached = Entity('old', 'cabinet', (0, 0, 1.08), (-.1, -.1, .92), (.1, .1, 1.13), visible=False)
    route = measured_side_route({'xyz': [0, 0, .91]}, [distant, cached], 'box', 1.2)
    assert route['waypoints'] == []


def test_cabinet_contact_retracts_to_measured_side_before_lifting():
    obj = Entity('box', 'box', (0, 0, .93), (-.03, -.02, .9), (.03, .02, .96))
    cabinet = Entity('cab', 'cabinet', (0, -.15, 1.08), (-.1, -.3, .92), (.1, -.04, 1.13))
    calls = []
    p = SimpleNamespace(_last_obs_eef_pos=np.array([.1, 0, 1.2]), _last_obs_gripper=.035,
        env=SimpleNamespace(raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.]},
                            terminated=False, truncated=False))

    def pose(xyz, **kwargs):
        p._last_obs_eef_pos = np.asarray(xyz, dtype=float)
        calls.append(('pose', list(xyz), kwargs['gripper']))
        return {'final_dist_m': 0., 'final_pitch': 0., 'final_yaw_err': 0.}

    def move(xyz, gripper, **kwargs):
        if gripper == 1:
            # The old direct lift had a palm overhang inside the cabinet
            # envelope; the corrected retreat must put it outside first.
            assert p._last_obs_eef_pos[1] > cabinet.upper[1] + .10
        p._last_obs_eef_pos = np.asarray(xyz, dtype=float)
        calls.append(('move', list(xyz), gripper))
        return {'waypoint_reached': True}

    p.move_pose = pose
    p.set_gripper = lambda **kw: calls.append(('gripper', kw)) or {}
    scene = SimpleNamespace(entities={obj.id: obj, cabinet.id: cabinet},
        measurement_clouds={obj.id: box_cloud()}, measurement_clouds_by_view={}, dual_view_fusion_v1=True)
    from robots.libero.v5_runtime import V5Executor

    executor = V5Executor(SimpleNamespace(primitives=p), scene,
        analytic_grasp_v1=True, analytic_side_route_v1=True)
    executor._refresh = lambda *args: None
    executor.move = move
    executor.verify_grasp_measurement = lambda *args: False
    execute_analytic_grasp(executor, obj, {})
    close = next(i for i, c in enumerate(calls) if c[0] == 'gripper')
    assert calls[close + 1][0] == 'pose'
    assert calls[close + 1][2] == 1
    assert executor.motion_evidence[-1]['analytic_stage'] == 'side_retreat'


def test_rotated_box_closes_across_narrow_axis_and_lifts_ten_centimetres():
    plan = top_grasp(box_cloud(), "box", [.1, .1, 1.2], .2)
    assert plan["valid"]
    assert plan["measured_width_m"] == pytest.approx(.035, abs=.004)
    assert abs(np.dot(plan["closing_axis_xy"], [np.cos(.7), np.sin(.7)])) < .05
    assert .93 < plan["xyz"][2] < .96
    assert plan["lift_m"] == .1
    from scipy.spatial.transform import Rotation
    body = Rotation.from_euler('z', plan['yaw']).as_matrix() @ Rotation.from_euler('x', np.pi).as_matrix()
    site = body @ Rotation.from_euler('z', -np.pi/2).as_matrix()
    assert abs(np.dot(site[:2, 0], plan['closing_axis_xy'])) == pytest.approx(1.)


def test_too_wide_top_does_not_attempt_closure():
    plan = top_grasp(box_cloud(width=.10, length=.18), "box", [0, 0, 1.2], 0)
    assert not plan["valid"]
    assert plan["reason"] == "measured_width_exceeds_gripper"


def test_supported_bottle_cap_survives_percentile_trimming_but_isolated_high_noise_does_not():
    rng = np.random.default_rng(63)
    body = rng.uniform([-.022, -.022, .90], [.022, .022, 1.04], (20000, 3))
    cap = rng.uniform([-.008, -.008, 1.052], [.008, .008, 1.056], (300, 3))
    points = np.concatenate([body, cap, [[0., 0., 1.24], [.003, 0., 1.30]]])
    old = top_grasp(points, "wine bottle", [0., 0., 1.2], 0.)
    new = top_grasp(points, "wine bottle", [0., 0., 1.2], 0., height_envelope=True)
    assert old["valid"] and new["valid"]
    assert old["measured_top_z"] < 1.04
    assert 1.052 < new["measured_top_z"] < 1.057
    assert new["height_source"] == "current_fused_rgbd_points"
    assert new["xyz"][2] > old["xyz"][2] + .015


def test_bottle_height_feature_does_not_change_box_contact():
    points = box_cloud()
    assert top_grasp(points, "box", [0., 0., 1.2], 0.) == top_grasp(
        points, "box", [0., 0., 1.2], 0., height_envelope=True)


def test_bowl_grips_local_rim_instead_of_rejecting_whole_diameter():
    rng = np.random.default_rng(8)
    angle = rng.uniform(0, 2*np.pi, 6000)
    radius = rng.uniform(.05, .06, 6000)
    points = np.c_[radius*np.cos(angle), radius*np.sin(angle), rng.uniform(.92, .96, 6000)]
    plan = top_grasp(points, "bowl", [.2, 0, 1.2], 0)
    assert plan["valid"]
    assert .045 < np.linalg.norm(plan["xyz"][:2]) < .065
    assert plan["measured_width_m"] < .03


def test_large_cup_uses_measured_rim_without_grasping_full_diameter():
    rng = np.random.default_rng(10)
    angle = rng.uniform(0, 2*np.pi, 6000)
    radius = rng.uniform(.045, .052, 6000)
    points = np.c_[radius*np.cos(angle), radius*np.sin(angle), rng.uniform(.92, 1.02, 6000)]
    plan = top_grasp(points, "white mug", [.2, 0, 1.2], 0)
    assert plan["valid"]
    assert plan["fit"] == "measured_rim_patch"
    assert plan["measured_width_m"] < .03


def test_large_pan_uses_measured_handle_and_rejects_handleless_body():
    rng = np.random.default_rng(12)
    angle = rng.uniform(0, 2*np.pi, 5000)
    radius = rng.uniform(.03, .10, 5000)
    body = np.c_[radius*np.cos(angle), radius*np.sin(angle), rng.uniform(.9, .94, 5000)]
    handle = rng.uniform([.10, -.014, .916], [.23, .014, .93], (3000, 3))
    plan = top_grasp(np.concatenate([body, handle]), "frypan", [0, 0, 1.2], 0)
    assert plan["valid"]
    assert plan["fit"] == "measured_handle_patch"
    assert plan["xyz"][0] > .15
    assert plan["measured_width_m"] < .04
    assert not top_grasp(body, "frypan", [0, 0, 1.2], 0)["valid"]


def test_failed_approach_never_calls_policy_or_closes():
    obj = Entity("e1", "box", (0, 0, .93), (-.03, -.02, .9), (.03, .02, .96))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([.1, 0, 1.2]),
        env=SimpleNamespace(raw_obs=lambda: {"robot0_eef_quat": [1., 0., 0., 0.]}))
    scene = SimpleNamespace(measurement_clouds={obj.id: box_cloud()},
        measurement_clouds_by_view={obj.id: {"agentview": {}, "wrist": {}}}, dual_view_fusion_v1=True)
    executor = SimpleNamespace(p=p, scene=scene, motion_evidence=[{"steps_used": 10}],
        move=lambda *args, **kwargs: {"waypoint_reached": False},
        vla_act=lambda *args, **kwargs: pytest.fail("analytic contact used VLA"))
    receipt = {}
    execute_analytic_grasp(executor, obj, receipt)
    assert receipt["failure_reason"] == "analytic_approach_not_reached"
    assert receipt["verification"] == "failed"


def test_unmeasured_handle_gets_close_wrist_view_before_contact_is_rejected(monkeypatch):
    obj = Entity('pan', 'frypan', (0, 0, .93), (-.1, -.1, .9), (.2, .1, .96))
    calls = []

    def fit(*args, **kwargs):
        calls.append('fit')
        return {'valid': False, 'reason': 'pan_handle_not_measured'}

    def refine(executor, before, hint):
        calls.append('wrist_refine')
        return {'private_pose_used': False}

    monkeypatch.setattr('robots.libero.v5_analytic_grasp.top_grasp', fit)
    monkeypatch.setattr('robots.libero.v5_grasp_public_tracking.refresh_grasp_target', refine)
    policy = SimpleNamespace(_last_obs_eef_pos=np.array([.1, 0, 1.2]),
        env=SimpleNamespace(raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.]}))
    scene = SimpleNamespace(entities={obj.id: obj}, measurement_clouds={obj.id: box_cloud()},
        measurement_clouds_by_view={}, dual_view_fusion_v1=True)

    def move(xyz, *args, **kwargs):
        calls.append('viewpoint_move')
        policy._last_obs_eef_pos = np.asarray(xyz)
        return {'waypoint_reached': True}

    executor = SimpleNamespace(p=policy, scene=scene, analytic_geometry_v1=True,
        toolkit=SimpleNamespace(_state=SimpleNamespace(save=lambda *args: None)),
        motion_evidence=[], move=move,
        _refresh=lambda *args: pytest.fail('unbounded identity refresh used'))
    receipt = {}
    execute_analytic_grasp(executor, obj, receipt)
    assert calls == ['fit', 'viewpoint_move', 'viewpoint_move', 'wrist_refine', 'fit']
    assert receipt['failure_reason'] == 'pan_handle_not_measured'
    assert receipt['grasp_verified'] is None
    assert 'analytic_close' not in receipt


def test_precontact_tracking_uses_prior_identity_not_category_only_refresh(monkeypatch):
    obj = Entity('e1', 'box', (0, 0, .93), (-.03, -.02, .9), (.03, .02, .96))
    queries = []

    def refresh(executor, before, closing):
        queries.append((before, closing.copy()))
        return {'private_pose_used': False}

    monkeypatch.setattr('robots.libero.v5_grasp_public_tracking.refresh_grasp_target', refresh)
    p = SimpleNamespace(_last_obs_eef_pos=np.array([.1, 0, 1.2]),
        env=SimpleNamespace(raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.]},
                            terminated=False, truncated=False),
        move_pose=lambda *args, **kwargs: {'final_dist_m': .1, 'final_pitch': 0., 'final_yaw_err': 0.})
    scene = SimpleNamespace(entities={obj.id: obj}, measurement_clouds={obj.id: box_cloud()},
        measurement_clouds_by_view={obj.id: {'agentview': {}, 'wrist': {}}}, dual_view_fusion_v1=True)
    executor = SimpleNamespace(p=p, scene=scene, motion_evidence=[], grasp_public_tracking_v1=True,
        move=lambda *args, **kwargs: {'waypoint_reached': True},
        _refresh=lambda *args: pytest.fail('category-only refresh could replace the selected identity'))
    receipt = {}
    execute_analytic_grasp(executor, obj, receipt)
    assert queries[0][0] == obj
    assert np.array_equal(queries[0][1], p._last_obs_eef_pos)
    assert receipt['precontact_identity']['phase'] == 'before_contact'
    assert receipt['failure_reason'] == 'analytic_orient_not_reached'


@pytest.mark.parametrize('precise,closes', [(False, True), (True, False)])
def test_shallow_contact_missed_by_five_mm_is_not_closed_in_precision_mode(precise, closes):
    obj = Entity('e1', 'box', (0, 0, .93), (-.03, -.02, .9), (.03, .02, .96))
    p = SimpleNamespace(_last_obs_eef_pos=np.array([.1, 0, 1.2]), _last_obs_gripper=.035,
        env=SimpleNamespace(raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.]},
                            terminated=False, truncated=False))
    closed = []

    def pose(xyz, **kwargs):
        p._last_obs_eef_pos = np.asarray(xyz, dtype=float)
        error = .0054 if xyz[2] < 1. else 0.
        return {'final_dist_m': error, 'final_pitch': 0., 'final_yaw_err': 0.}

    p.move_pose = pose
    p.set_gripper = lambda **kwargs: closed.append(kwargs) or {}
    scene = SimpleNamespace(entities={obj.id: obj}, measurement_clouds={obj.id: box_cloud()},
                            measurement_clouds_by_view={}, dual_view_fusion_v1=True)
    executor = SimpleNamespace(p=p, scene=scene, motion_evidence=[],
        analytic_contact_precision_v1=precise, _refresh=lambda *args: None,
        move=lambda *args, **kwargs: {'waypoint_reached': True},
        verify_grasp_measurement=lambda *args: False)
    receipt = {}
    execute_analytic_grasp(executor, obj, receipt)
    assert bool(closed) is closes
    if precise:
        assert receipt['failure_reason'] == 'analytic_descend_not_reached'
        assert receipt['verification'] == 'failed'
