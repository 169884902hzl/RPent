from dataclasses import replace
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_grasp_observation import refine_unified_grasp_views
from robots.libero.v5_state import Entity


def test_extra_views_share_finite_existing_budget_and_execute_only_screened_routes(monkeypatch):
    from robots.libero import v5_geometric_grasp as geometry
    from robots.libero import v5_grasp_geometry as perception
    from robots.libero import v5_grasp_kinematics as kinematics
    from robots.libero import v5_grasp_public_tracking as tracking
    from robots.libero import v5_grasp_route as route

    obj = Entity('e1', 'arbitrary object', (0, 0, .93), (-.03, -.02, .9), (.03, .02, .96))
    points = np.array([[x, y, .93] for x in (-.02, 0., .02) for y in (-.01, .01)])
    scene = SimpleNamespace(entities={obj.id: obj}, measurement_clouds={obj.id: points})
    env = SimpleNamespace(terminated=False, truncated=False,
        raw_obs=lambda: {'robot0_eef_quat': [1., 0., 0., 0.], 'robot0_joint_pos': [0.]*7})
    policy = SimpleNamespace(env=env, _last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.08)
    requests = []

    def servo(policy, xyz, quat, **kwargs):
        requests.append(kwargs['max_steps'])
        policy._last_obs_eef_pos = np.array(xyz)
        return {'actions_used': min(2, kwargs['max_steps']), 'final_dist_m': 0.,
                'final_orientation_err_rad': 0.}

    def refresh(executor, before, closing):
        executor.scene.entities[before.id] = replace(before, source_step=before.source_step+1)
        return {'source': 'test_public_measurement'}

    monkeypatch.setattr(geometry, 'panda_geometry', lambda path: {'site_offset_in_gripper_m': [0.]*3})
    monkeypatch.setattr(geometry, 'remove_measured_hand', lambda world, *args: (world, {}))
    monkeypatch.setattr(geometry, 'servo_grasp_pose', servo)
    monkeypatch.setattr(perception, 'oblique_target_view', lambda before, axis, xyz, quat, meta, sign:
        {'xyz': [.1*sign, 0., 1.15], 'body_quat_xyzw': quat, 'sign': sign})
    monkeypatch.setattr(kinematics, 'PublicPoseScreen', lambda *args: SimpleNamespace(
        remove_measured_arm=lambda world: (world, {})))
    monkeypatch.setattr(route, 'sweep_route', lambda xyz, quat, path, *args, **kwargs:
        (True, {'execution_waypoints': path}))
    monkeypatch.setattr(tracking, 'refresh_grasp_target', refresh)
    executor = SimpleNamespace(p=policy, scene=scene, geometric_gripper_xml='/robot/grippers/panda.xml',
        motion_evidence=[], toolkit=SimpleNamespace(_state=SimpleNamespace(load=lambda name: points)),
        capture=lambda: None)
    receipt = {}
    result = refine_unified_grasp_views(executor, obj, receipt, 5)
    assert requests == [5, 3, 1]
    assert result.name == 'arbitrary object'
    assert receipt['geometric_active_views']['control_steps_used'] == 5
    assert receipt['geometric_active_views']['remaining_refinement_steps'] == 0
    assert len(receipt['geometric_active_views']['views']) == 1
    assert len(executor.motion_evidence) == 3
