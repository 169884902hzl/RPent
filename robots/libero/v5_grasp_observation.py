# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Generic additional RGB-D views inside the existing refinement-step budget."""
from dataclasses import replace
from pathlib import Path

import numpy as np


def refine_unified_grasp_views(executor, before, receipt, remaining_steps):
    """Observe both PCA flanks; every route needs a swept mesh and public IK."""
    from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand, servo_grasp_pose
    from robots.libero.v5_grasp_geometry import oblique_target_view
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen
    from robots.libero.v5_grasp_public_tracking import refresh_grasp_target
    from robots.libero.v5_grasp_route import sweep_route

    initial = np.asarray(executor.scene.measurement_clouds[before.id])
    _, axes = np.linalg.eigh(np.cov(initial[:, :2].T))
    clouds, observations = [initial], [before.source_step]
    geometry = panda_geometry(executor.geometric_gripper_xml)
    state = executor.toolkit._state
    evidence = {'version': 'public-generic-opposing-observation-views/1-dev',
        'source': 'stationary_current_rgbd_and_public_robot_sensors',
        'remaining_refinement_budget_at_entry': remaining_steps,
        'control_steps_used': 0, 'views': [], 'private_pose_used': False}
    receipt['geometric_active_views'] = evidence
    for sign in (-1, 1):
        if remaining_steps <= 0 or executor.p.env.terminated or executor.p.env.truncated:
            break
        observed = executor.p.env.raw_obs()
        xyz, quat = executor.p._last_obs_eef_pos.copy(), observed['robot0_eef_quat']
        view = oblique_target_view(before, axes[:, 0], xyz, quat, state.load('wrist_metadata.json'), sign)
        safe = max(float(xyz[2]), view['xyz'][2])
        path = [{'phase': 'view_raise', 'xyz': [*xyz[:2], safe], 'body_quat_xyzw': list(quat)},
                {'phase': 'view_transit', 'xyz': [*view['xyz'][:2], safe],
                 'body_quat_xyzw': view['body_quat_xyzw']},
                {'phase': 'view_measure', 'xyz': view['xyz'],
                 'body_quat_xyzw': view['body_quat_xyzw']}]
        world = np.concatenate([np.asarray(state.load(c+'_world_high.npz')).reshape(-1, 3)
                                for c in ('agentview', 'wrist')])
        world, _ = remove_measured_hand(world, xyz, quat, geometry, executor.p._last_obs_gripper)
        robot_xml = Path(executor.geometric_gripper_xml).parent.parent/'robots/panda/robot.xml'
        screen = PublicPoseScreen(robot_xml, observed['robot0_joint_pos'], xyz, quat,
                                  geometry['site_offset_in_gripper_m'])
        world, arm_filter = screen.remove_measured_arm(world)
        passed, checked = sweep_route(xyz, quat, path, world, np.empty((0, 3)), geometry,
                                      pose_screen=screen)
        detail = {'pose': view, 'route_screen': checked, 'current_robot_filter': arm_filter}
        evidence['views'].append(detail)
        if not passed:
            detail['rejected'] = checked['reason']
            continue
        reached = True
        for waypoint in checked['execution_waypoints']:
            if remaining_steps <= 0 or executor.p.env.terminated or executor.p.env.truncated:
                reached = False
                break
            options = {}
            if getattr(executor, 'motion_trace_v1', False):
                options.update(trace_steps=True, motion_diagnostic=lambda: executor.p.env._client.call(
                    'diagnostic.motion', timeout_s=30))
            result = servo_grasp_pose(executor.p, waypoint['xyz'], waypoint['body_quat_xyzw'],
                gripper=-1., max_steps=min(80, remaining_steps), tol=.008, ori_tol=.05, **options)
            executor.motion_evidence.append({**result, 'analytic_stage': 'generic_observation_'+waypoint['phase']})
            remaining_steps -= result['actions_used']
            evidence['control_steps_used'] += result['actions_used']
            if result['final_dist_m'] > .015 or result['final_orientation_err_rad'] > .08:
                reached = False
                break
        if not reached:
            detail['rejected'] = 'observation_route_not_reached_within_existing_budget'
            executor.capture()
            continue
        detail['identity'] = refresh_grasp_target(executor, before, executor.p._last_obs_eef_pos.copy())
        current = executor.scene.entities.get(before.id)
        if current is None or not current.visible:
            detail['rejected'] = 'stationary_target_not_measured'
            continue
        clouds.append(np.asarray(executor.scene.measurement_clouds[before.id]))
        observations.append(current.source_step)
    points = np.concatenate(clouds)
    lower, upper = np.quantile(points, (.02, .98), axis=0)
    measured = replace(before, xyz=tuple(np.median(points, axis=0)), lower=tuple(lower),
        upper=tuple(upper), visible=True, source_step=observations[-1],
        geometry='stationary_precontact_multiframe_rgbd')
    executor.scene.entities[before.id] = measured
    executor.scene.measurement_clouds[before.id] = points
    evidence.update(observation_steps=observations, measured_points=len(points),
                    remaining_refinement_steps=remaining_steps)
    return measured
