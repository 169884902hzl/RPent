# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Development top grasps from measured, world-frame RGB-D points only."""

from __future__ import annotations

import math

import numpy as np

VERSION = "rgbd-analytic-top-grasp/2-dev"
# Panda gripper XML: two slide joints travel 0.04 m each. The finger
# bodies rotate +90 degrees about EEF z, so closure is along EEF x.
MAX_OPENING_M = .08
PAD_ABOVE_TCP_M = .0036
PALM_CLEARANCE_M = .11  # panda hand.stl: longest measured half extent .104 m.


def measured_side_route(plan: dict, entities, target_id: str, height: float) -> dict:
    """Enter between open fingers, along the measured object's tangent axis."""
    target = np.asarray(plan["xyz"], dtype=float)
    obstacles = [e for e in entities if e.id != target_id and e.visible
        and any(word in e.name.lower() for word in ("cabinet", "drawer", "microwave"))
        and e.upper[2] > target[2] + .03
        and all(e.lower[i] - PALM_CLEARANCE_M <= target[i]
                <= e.upper[i] + PALM_CLEARANCE_M for i in (0, 1))]
    if not obstacles:
        return {"version": "public-furniture-side-route/2-dev", "source": "perception",
                "waypoints": [], "obstacles": []}
    closure = np.asarray(plan['closing_axis_xy'], dtype=float)
    if closure.shape != (2,) or not np.isfinite(closure).all() or np.linalg.norm(closure) < 1e-6:
        raise ValueError('measured planar closing axis required for side entry')
    closure /= np.linalg.norm(closure)
    tangent = np.array([-closure[1], closure[0]])
    choices = []
    for sign in (-1, 1):
        direction = sign * tangent
        exits = []
        for entity in obstacles:
            distances = [(entity.upper[axis] + PALM_CLEARANCE_M - target[axis]) / direction[axis]
                         if direction[axis] > 0 else
                         (entity.lower[axis] - PALM_CLEARANCE_M - target[axis]) / direction[axis]
                         for axis in (0, 1) if abs(direction[axis]) > 1e-6]
            exits.append(min(distances))
        point = target.copy()
        point[:2] += direction * max(exits)
        choices.append(point)
    side = min(choices, key=lambda p: float(np.linalg.norm(p[:2] - target[:2])))
    safe_height = max(height, max(e.upper[2] for e in obstacles) + .15)
    return {"version": "public-furniture-side-route/2-dev", "source": "perception",
            "private_pose_used": False,
            "entry_axis_basis": "perpendicular_to_measured_gripper_closing_axis",
            "closing_axis_xy": closure.tolist(),
            "obstacles": [{"id": e.id, "lower": list(e.lower), "upper": list(e.upper),
                           "source_step": e.source_step} for e in obstacles],
            "waypoints": [("side_above", [*side[:2], safe_height]),
                          ("side_descend", side.tolist()),
                          ("side_contact", target.tolist())],
            "terminal_clearance_verified": False}


def top_grasp(points, name: str, eef_xyz, current_yaw: float, *, height_envelope: bool = False,
              connected_handle: bool = False) -> dict:
    """Fit a top/edge grasp; no simulator entities, targets or task assets."""
    cloud = np.asarray(points, dtype=float)
    if cloud.ndim != 2 or cloud.shape[1] != 3:
        raise ValueError("expected measured world-frame Nx3 points")
    cloud = cloud[np.isfinite(cloud).all(axis=1)]
    if len(cloud) < 40:
        return {"version": VERSION, "valid": False, "reason": "insufficient_measured_points"}
    lower, upper = np.quantile(cloud, [.02, .98], axis=0)
    envelope = height_envelope and 'bottle' in name
    if envelope:
        from scipy.spatial import cKDTree

        # A narrow bottle cap occupies few pixels. Trimming its upper tail and
        # using z-p95 can lower the commanded palm into the visible cap.
        # Keep the supported upper surface, rejecting isolated depth outliers.
        cloud = cloud[((cloud[:, :2] >= lower[:2]) & (cloud[:, :2] <= upper[:2])).all(axis=1)
                      & (cloud[:, 2] >= lower[2])]
        if len(cloud) < 30:
            return {"version": VERSION, "valid": False, "reason": "insufficient_trimmed_points"}
        supported = cKDTree(cloud).query_ball_point(cloud, r=.004, return_length=True) >= 10
        cloud = cloud[supported]
    else:
        cloud = cloud[((cloud >= lower) & (cloud <= upper)).all(axis=1)]
    if len(cloud) < 30:
        return {"version": VERSION, "valid": False, "reason": "insufficient_trimmed_points"}
    centre = (lower[:2] + upper[:2]) / 2
    _, vectors = np.linalg.eigh(np.cov(cloud[:, :2].T))
    closure = vectors[:, 0]
    top = float(np.quantile(cloud[:, 2], .99 if envelope else .95))
    height = float(top - lower[2])
    if height < .008:
        return {"version": VERSION, "valid": False, "reason": "height_not_measured",
                "measured_height_m": height}
    band = cloud[cloud[:, 2] >= top - min(.02, height * .3)]
    if len(band) < 15:
        return {"version": VERSION, "valid": False, "reason": "top_not_measured"}
    rim = any(word in name for word in ("bowl", "ramekin", "mug", "cup"))
    pan = any(word in name for word in ("frypan", "frying pan", "skillet"))
    handle = False
    handle_evidence = None
    if pan and connected_handle:
        from robots.libero.v5_grasp_geometry import measure_pan_handle
        measured, handle_evidence = measure_pan_handle(cloud)
        if measured is None:
            return {"version": VERSION, "valid": False, "reason": "pan_handle_not_measured",
                    "handle_geometry": handle_evidence}
        band, centre, closure = measured['points'], measured['centre_xy'], measured['closing_axis_xy']
        top = float(np.quantile(band[:, 2], .95))
        handle = True
    elif pan:
        # A pan body exceeds the physical gripper aperture. Only accept a
        # measured narrow extension of its PCA footprint, never its centre.
        major = vectors[:, 1]
        axis_projection = (cloud[:, :2] - centre) @ major
        patches = []
        for sign in (-1, 1):
            projection = sign * axis_projection
            low, high = np.quantile(projection, [.90, .99])
            patch = cloud[(projection >= low) & (projection <= high)]
            if len(patch) < 20 or high - low < .012:
                continue
            patch_centre = np.median(patch[:, :2], axis=0)
            cross = (patch[:, :2] - patch_centre) @ closure
            patch_width = float(np.quantile(cross, .98) - np.quantile(cross, .02))
            if .008 < patch_width < MAX_OPENING_M - .008:
                patches.append((patch_width, patch, patch_centre))
        if not patches:
            return {"version": VERSION, "valid": False, "reason": "pan_handle_not_measured"}
        _, band, centre = min(patches, key=lambda item: item[0])
        top = float(np.quantile(band[:, 2], .95))
        handle = True
    elif rim:
        radial = band[:, :2] - centre
        radius = np.linalg.norm(radial, axis=1)
        edge = band[radius >= np.quantile(radius, .65)]
        # Pick a measured rim near the current robot, rather than grip the
        # entire bowl diameter. Closure crosses the local rim radially.
        rim_point = edge[np.argmin(np.linalg.norm(edge[:, :2] - np.asarray(eef_xyz)[:2], axis=1))]
        radial_axis = rim_point[:2] - centre
        if np.linalg.norm(radial_axis) < .01:
            return {"version": VERSION, "valid": False, "reason": "rim_not_measured"}
        closure = radial_axis / np.linalg.norm(radial_axis)
        tangent = np.array([-closure[1], closure[0]])
        delta = edge[:, :2] - rim_point[:2]
        patch = edge[(np.abs(delta @ tangent) <= .012) & (np.abs(delta @ closure) <= .02)]
        if len(patch) < 8:
            return {"version": VERSION, "valid": False, "reason": "rim_patch_not_measured"}
        centre = np.median(patch[:, :2], axis=0)
        band = patch
        top = float(np.quantile(patch[:, 2], .8))
    else:
        # The top footprint centres the contact independently of the visible
        # side-surface median stored in the entity's general position.
        centre = (np.quantile(band[:, :2], .05, axis=0)
                  + np.quantile(band[:, :2], .95, axis=0)) / 2
    projection = (band[:, :2] - centre) @ closure
    width = float(np.quantile(projection, .98) - np.quantile(projection, .02))
    if width + .008 >= MAX_OPENING_M:
        return {"version": VERSION, "valid": False, "reason": "measured_width_exceeds_gripper",
                "measured_width_m": width, "maximum_opening_m": MAX_OPENING_M}
    # robot0_eef_quat is the hand BODY orientation. The grip site rotates
    # -90 degrees from it; for a downward wrist the closing axis is therefore
    # perpendicular to the observed body's x axis (parallel-jaw sign is free).
    yaw = math.atan2(float(closure[1]), float(closure[0])) + math.pi / 2
    # Parallel-jaw poses differing by pi grasp the same patch. Choose the
    # smaller public wrist rotation instead of forcing a yaw_90 transition.
    yaw += round((current_yaw - yaw) / math.pi) * math.pi
    depth = min(.015 if rim else .025, height * .25)
    xyz = [float(centre[0]), float(centre[1]), top - depth - PAD_ABOVE_TCP_M]
    return {"version": VERSION, "valid": True, "source": "perception",
            **({'handle_geometry': handle_evidence} if handle_evidence is not None else {}),
            **({"height_estimator": "measured_supported_upper_tail/1-dev",
                "height_source": "current_fused_rgbd_points", "supported_top_quantile": .99}
               if envelope else {}),
            "fit": "measured_handle_patch" if handle else "measured_rim_patch" if rim else "measured_top_pca",
            "points": len(cloud), "top_points": len(band), "xyz": xyz,
            "yaw": yaw, "closing_axis_xy": closure.tolist(), "measured_width_m": width,
            "maximum_opening_m": MAX_OPENING_M, "measured_top_z": top,
            "measured_height_m": height, "lift_m": .10,
            "robot_geometry": "panda_gripper.xml: observed BODY quat; body-to-site Rz(-pi/2), closing site x, pad z=.0934 vs site z=.097"}


def execute_analytic_grasp(executor, obj, receipt: dict) -> None:
    """Stage, close and lift using the existing public servo and verifier."""
    from scipy.spatial.transform import Rotation

    def fit(entity, *, sample_candidates=True):
        points = executor.scene.measurement_clouds.get(entity.id)
        if points is None:
            return {"version": VERSION, "valid": False, "reason": "current_cloud_missing"}
        rotation = Rotation.from_quat(executor.p.env.raw_obs()["robot0_eef_quat"]).as_matrix()
        yaw = math.atan2(rotation[1, 0], rotation[0, 0])
        unified = getattr(executor, 'unified_grasp_route_v1', False)
        if unified:
            # A generic public upper extent locates the refinement view.
            # Contact patches and category-specific segmentation live in perception.
            cloud = np.asarray(points)
            if len(cloud)<40:
                return {'version': 'public-full-route-grasp/1-dev', 'valid':False,
                        'reason':'insufficient_measured_surface'}
            result = {'version': 'public-full-route-grasp/1-dev', 'valid': len(cloud) >= 40,
                      'xyz': np.median(cloud,axis=0).tolist(),
                      'measured_top_z': float(np.quantile(cloud[:,2],.98)),
                      'reason': 'insufficient_measured_surface' if len(cloud)<40 else None}
        else:
            result = top_grasp(points, entity.name, executor.p._last_obs_eef_pos, yaw,
                height_envelope=getattr(executor, 'analytic_height_envelope_v1', False),
                connected_handle=getattr(executor, 'analytic_geometry_v1', False))
        if getattr(executor, 'analytic_geometry_v1', False):
            executor.toolkit._state.save('analytic_target_' + entity.id + '.npz', np.asarray(points))
        if (unified or getattr(executor, 'geometric_grasp_sampling_v1', False)) and sample_candidates:
            from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand, sample_grasps
            geometry = panda_geometry(executor.geometric_gripper_xml)
            public_world = []
            for camera in ('agentview', 'wrist'):
                world = executor.toolkit._state.load(camera + '_world_high.npz')
                public_world.append(np.asarray(world).reshape(-1, 3))
            observation = executor.p.env.raw_obs()
            visible_scene, self_points = remove_measured_hand(np.concatenate(public_world),
                executor.p._last_obs_eef_pos, observation['robot0_eef_quat'], geometry,
                executor.p._last_obs_gripper)
            pose_screen = None
            arm_filter = None
            if unified or getattr(executor, 'geometric_pose_screen_v1', False):
                from pathlib import Path
                from robots.libero.v5_grasp_kinematics import PublicPoseScreen
                robot_xml = Path(executor.geometric_gripper_xml).parent.parent / 'robots/panda/robot.xml'
                pose_screen = PublicPoseScreen(robot_xml, observation['robot0_joint_pos'],
                    executor.p._last_obs_eef_pos, observation['robot0_eef_quat'],
                    geometry['site_offset_in_gripper_m'])
                if unified:
                    visible_scene, arm_filter = pose_screen.remove_measured_arm(visible_scene)
            if unified:
                from robots.libero.v5_grasp_route import sample_unified_grasps
                fitted,candidates = sample_unified_grasps(points,visible_scene,entity.name,
                    executor.p._last_obs_eef_pos,observation['robot0_eef_quat'],geometry,pose_screen,height)
            else:
                fitted, candidates = sample_grasps(points, visible_scene, entity.name,
                    executor.p._last_obs_eef_pos, yaw, geometry,
                    current_body_quat_xyzw=observation['robot0_eef_quat'],
                    **({'pose_screen': pose_screen, 'approach_height': height} if pose_screen is not None else {}))
            receipt.setdefault('geometric_grasp_rankings', []).append({
                'entity': entity.id, 'measurement_step': entity.source_step,
                'candidates': candidates, 'removed_current_hand_points': self_points,
                'current_robot_arm_filter': arm_filter,
                'private_pose_used': False})
            result = fitted if fitted is not None else {
                'version': 'public-geometric-grasp/1-dev', 'valid': False,
                'reason': 'no_collision_free_opposing_grasp'}
        result.update(entity=entity.id, measurement_step=entity.source_step,
                      measured_entity_xyz=list(entity.xyz), measured_lower=list(entity.lower),
                      measured_upper=list(entity.upper),
                      fusion_version="rgbd_dual_view/1" if executor.scene.dual_view_fusion_v1 else "single_view",
                      cameras=sorted(executor.scene.measurement_clouds_by_view.get(entity.id, {})))
        return result

    # Sample contact poses after the close wrist measurement. A missing
    # opposing flank or handle in the distant view is a reason to refine,
    # not a reason to invent a contact pose from that view.
    plan = fit(obj, sample_candidates=False)
    receipt.update(grasp_contact_method=VERSION, analytic_grasp_plan=plan)
    receipt['analytic_initial_plan'] = plan
    if not plan['valid'] and (getattr(executor, 'geometric_grasp_sampling_v1', False)
                             or getattr(executor, 'analytic_geometry_v1', False)):
        receipt['initial_geometry_deferred_for_wrist_measurement'] = plan
        plan = {'valid': True, 'viewpoint_only': True, 'source': 'perception',
                'xyz': [(obj.lower[0] + obj.upper[0])/2, (obj.lower[1] + obj.upper[1])/2,
                        obj.upper[2]], 'measured_top_z': obj.upper[2]}
    if not plan["valid"]:
        receipt.update(grasp_verified=None, verification="unmeasured", failure_reason=plan["reason"])
        return
    current = executor.p._last_obs_eef_pos.copy()
    height = max(float(current[2]), plan["measured_top_z"] + .15)
    if getattr(executor,'unified_grasp_route_v1',False):
        from pathlib import Path
        from robots.libero.v5_geometric_grasp import panda_geometry, remove_measured_hand
        from robots.libero.v5_grasp_kinematics import PublicPoseScreen
        from robots.libero.v5_grasp_route import sweep_route
        geometry=panda_geometry(executor.geometric_gripper_xml)
        observation=executor.p.env.raw_obs()
        scene_cloud=np.concatenate([np.asarray(executor.toolkit._state.load(c+'_world_high.npz')).reshape(-1,3)
                                   for c in ('agentview','wrist')])
        scene_cloud=scene_cloud[np.isfinite(scene_cloud).all(axis=1)&(np.linalg.norm(scene_cloud,axis=1)>1e-6)]
        scene_cloud,_=remove_measured_hand(scene_cloud,current,observation['robot0_eef_quat'],geometry,
                                         executor.p._last_obs_gripper)
        robot_xml=Path(executor.geometric_gripper_xml).parent.parent/'robots/panda/robot.xml'
        screen=PublicPoseScreen(robot_xml,observation['robot0_joint_pos'],current,
                                observation['robot0_eef_quat'],geometry['site_offset_in_gripper_m'])
        scene_cloud, arm_filter = screen.remove_measured_arm(scene_cloud)
        receipt['refinement_view_current_arm_filter'] = arm_filter
        viewpoint=[{'phase':'view_raise','xyz':[current[0],current[1],height],
                    'body_quat_xyzw':list(observation['robot0_eef_quat'])},
                   {'phase':'view_translate','xyz':[*plan['xyz'][:2],height],
                    'body_quat_xyzw':list(observation['robot0_eef_quat'])}]
        valid,evidence=sweep_route(current,observation['robot0_eef_quat'],viewpoint,scene_cloud,
                                   np.empty((0,3)),geometry,pose_screen=screen)
        receipt['refinement_view_route_screen']=evidence
        if not valid:
            receipt.update(grasp_verified=False,verification='failed',failure_reason='refinement_route_'+evidence['reason'])
            return
    active_views = (getattr(executor, 'unified_grasp_route_v1', False)
                    and getattr(executor, 'geometric_grasp_active_views_v1', False))
    view_steps_before = executor.p.env.execution_budget()['used_sim_steps'] if active_views else None
    for target in ([current[0], current[1], height], [*plan["xyz"][:2], height]):
        result = executor.move(target, -1, recoverable=True, tolerance_m=.015)
        receipt["executed"] = bool(executor.motion_evidence)
        if not result.get("waypoint_reached"):
            receipt.update(grasp_verified=False, verification="failed", failure_reason="analytic_approach_not_reached")
            return
    # One close wrist measurement refines the selected identity; neither
    # detector labels nor the server's private grasp labels control motion.
    if (getattr(executor, 'grasp_public_tracking_v1', False)
            or getattr(executor, 'analytic_identity_guard_v1', False)
            or getattr(executor, 'analytic_geometry_v1', False)):
        from robots.libero.v5_grasp_public_tracking import refresh_grasp_target

        # No contact has happened: the prior measured extent, rather than a
        # new category-only maximum score, identifies this stationary target.
        evidence = refresh_grasp_target(executor, obj, executor.p._last_obs_eef_pos.copy())
        receipt['precontact_identity'] = {**evidence, 'phase': 'before_contact',
            'hint_source': 'previous_measured_stationary_target_bounds'}
    else:
        executor._refresh([obj.name])
    measured = executor.scene.entities.get(obj.id)
    if measured is None or not measured.visible:
        receipt.update(grasp_verified=None, verification="unmeasured", failure_reason="analytic_refinement_missing")
        return
    obj = measured
    plan = fit(obj)
    if active_views and not plan['valid']:
        from robots.libero.v5_grasp_observation import refine_unified_grasp_views

        # The original two viewpoint servos each allow 80 steps. Additional
        # measured views share that 160-step allowance; contact remains 300.
        used = executor.p.env.execution_budget()['used_sim_steps']-view_steps_before
        obj = refine_unified_grasp_views(executor, obj, receipt, max(0, 160-used))
        receipt['refinement_step_budget'] = {'limit': 160, 'initial_steps_used': used,
            'additional_steps_used': receipt['geometric_active_views']['control_steps_used']}
        plan = fit(obj)
    if (not getattr(executor, 'unified_grasp_route_v1', False) and not plan['valid']
            and getattr(executor, 'geometric_grasp_active_views_v1', False)
            and obj.name in ('butter', 'cream cheese', 'chocolate pudding', 'box')):
        obj = refine_box_grasp_views(executor, obj, receipt)
        plan = fit(obj)
    receipt["analytic_grasp_plan"] = plan
    if not plan["valid"]:
        receipt.update(grasp_verified=None, verification="unmeasured", failure_reason=plan["reason"])
        return
    trace_options = {}
    if getattr(executor, 'motion_trace_v1', False):
        trace_options.update(trace_steps=True, motion_diagnostic=lambda: executor.p.env._client.call(
            'diagnostic.motion', timeout_s=30))
    unified = getattr(executor, 'unified_grasp_route_v1', False)
    stages = ([(waypoint['phase'], waypoint['xyz']) for waypoint in plan['route']] if unified else
              [("orient", [*plan["xyz"][:2], height]), ("descend", plan["xyz"])])
    if not unified and plan.get('sampled_approach', 'top') != 'top':
        entry = plan['approach_xyz']
        stages = [('sampled_side_above', [*entry[:2], height]),
                  ('sampled_side_descend', entry), ('sampled_side_contact', plan['xyz'])]
    if not unified and getattr(executor, 'analytic_side_route_v1', False):
        route = measured_side_route(plan, executor.scene.entities.values(), obj.id, height)
        receipt['analytic_side_route'] = route
        if route['waypoints']:
            stages = route['waypoints']
    route_steps_remaining = 300  # Original two contact-route servos: 2 x 150.
    for stage, xyz in stages:
        # The shallow top patch can be only a few millimetres deep. A coarse
        # approach tolerance can leave the contact on the outer finger mesh.
        contact_stage = (next(w.get('contact_endpoint',False) for w in plan['route'] if w['phase']==stage)
                         if unified else stage in ('descend','side_descend','side_contact','sampled_side_contact'))
        precise_contact = getattr(executor, 'analytic_contact_precision_v1', False) and contact_stage
        tolerance = .002 if precise_contact else .008
        if unified or plan.get('orientation') == 'horizontal_fingers':
            from robots.libero.v5_geometric_grasp import servo_grasp_pose
            quaternion = (next(w['body_quat_xyzw'] for w in plan['route'] if w['phase']==stage)
                          if unified else plan['body_quat_xyzw'])
            if unified and route_steps_remaining<=0:
                receipt.update(grasp_verified=False,verification='failed',failure_reason='analytic_route_budget_exhausted')
                return
            result = servo_grasp_pose(executor.p, xyz, quaternion,
                                     gripper=-1., tol=tolerance, ori_tol=.05,
                                     max_steps=min(150,route_steps_remaining) if unified else 150,
                                     **trace_options)
            orientation_missed = result['final_orientation_err_rad'] > .08
        else:
            result = executor.p.move_pose(xyz, target_pitch=0., target_yaw=plan["yaw"],
                                         gripper=-1., tol=tolerance, ori_tol=.05, max_steps=150,
                                         **trace_options)
            orientation_missed = abs(result['final_pitch']) > .08 or abs(result['final_yaw_err']) > .08
        executor.motion_evidence.append({**result, "analytic_stage": stage, "target_xyz": xyz})
        if unified:
            route_steps_remaining-=result['actions_used']
            receipt['route_servo_steps_used']=300-route_steps_remaining
        accepted_distance = tolerance if precise_contact else .015
        if (result["final_dist_m"] > accepted_distance or orientation_missed
                or executor.p.env.terminated or executor.p.env.truncated):
            receipt.update(grasp_verified=False, verification="failed", failure_reason=f"analytic_{stage}_not_reached")
            return
    executor.grasp_public_closing_xyz = executor.p._last_obs_eef_pos.copy()
    receipt["analytic_close"] = executor.p.set_gripper(gripper=1., steps=20)
    if not unified and getattr(executor, 'analytic_side_route_v1', False) and route['waypoints']:
        # Reverse the measured approach at contact height before raising the
        # palm back alongside the cabinet protrusion that blocked descent.
        retreat = [*route['waypoints'][-2][1][:2], float(executor.p._last_obs_eef_pos[2])]
        result = executor.p.move_pose(retreat, target_pitch=0., target_yaw=plan['yaw'],
                                     gripper=1., tol=.008, ori_tol=.05, max_steps=150,
                                     **trace_options)
        executor.motion_evidence.append({**result, 'analytic_stage': 'side_retreat', 'target_xyz': retreat})
        if (result['final_dist_m'] > .015 or abs(result['final_pitch']) > .08
                or abs(result['final_yaw_err']) > .08
                or executor.p.env.terminated or executor.p.env.truncated):
            receipt.update(grasp_verified=False, verification='failed', failure_reason='analytic_side_retreat_not_reached')
            return
    lift = executor.p._last_obs_eef_pos.copy()
    lift[2] += plan["lift_m"]
    result = executor.move(lift, 1., recoverable=True, tolerance_m=.015)
    if not result.get("waypoint_reached"):
        receipt.update(grasp_verified=False, verification="failed", failure_reason="analytic_lift_not_reached")
        return
    executor.p.set_gripper(gripper=1., steps=10)
    executor._refresh([obj.name])
    verified = executor.verify_grasp_measurement(obj)
    after = executor.scene.entities.get(obj.id)
    receipt.update(executed=True, grasp_verified=verified,
                   verification="unmeasured" if verified is None else "verified" if verified else "failed",
                   gripper_opening=round(executor.p._last_obs_gripper, 4),
                   measured_z_rise_cm=round((after.xyz[2] - obj.xyz[2]) * 100, 2)
                   if after and after.visible else None)
    executor.held = obj.id if verified else None
    executor.held_offset = (executor.p._last_obs_eef_pos.copy() - np.asarray([
        (after.lower[0] + after.upper[0]) / 2, (after.lower[1] + after.upper[1]) / 2,
        after.xyz[2]]) if verified else None)


def refine_box_grasp_views(executor, before, receipt):
    """Measure both narrow flanks before sampling; preserve stationary identity."""
    from dataclasses import replace
    from scipy.spatial.transform import Rotation, Slerp
    from robots.libero.v5_geometric_grasp import (
        collision_counts, panda_geometry, remove_measured_hand, servo_grasp_pose,
    )
    from robots.libero.v5_grasp_geometry import oblique_box_view
    from robots.libero.v5_grasp_public_tracking import refresh_grasp_target

    state = executor.toolkit._state
    geometry = panda_geometry(executor.geometric_gripper_xml)
    initial = np.asarray(executor.scene.measurement_clouds[before.id])
    _, axes = np.linalg.eigh(np.cov(initial[:, :2].T))
    narrow = axes[:, 0]
    clouds = [initial]
    observations = [{'source_step': before.source_step, 'points': len(initial),
                     'cameras': sorted(executor.scene.measurement_clouds_by_view.get(before.id, {}))}]
    evidence = {'version': 'public-box-opposing-oblique-views/1-dev',
                'source': 'stationary_public_rgbd_before_contact', 'views': [],
                'private_pose_used': False}
    for sign in (-1, 1):
        observed = executor.p.env.raw_obs()
        view = oblique_box_view(before, narrow, executor.p._last_obs_eef_pos,
                               observed['robot0_eef_quat'], state.load('wrist_metadata.json'), sign)
        eef = executor.p._last_obs_eef_pos.copy()
        rotations = Rotation.from_quat([observed['robot0_eef_quat'], view['body_quat_xyzw']])
        public_world = np.concatenate([np.asarray(state.load(camera + '_world_high.npz')).reshape(-1, 3)
                                       for camera in ('agentview', 'wrist')])
        visible, _ = remove_measured_hand(public_world, eef, observed['robot0_eef_quat'],
                                          geometry, executor.p._last_obs_gripper)
        # Check the visible hand sweep as well as its final observation pose.
        # This certifies neither hidden scene geometry nor arm-link reachability.
        collisions = []
        for fraction, body in zip(np.linspace(0., 1., 16), Slerp([0., 1.], rotations)(np.linspace(0., 1., 16))):
            position = eef + fraction * (np.asarray(view['xyz']) - eef)
            site = body.as_matrix() @ Rotation.from_euler('z', -math.pi/2).as_matrix()
            hits = collision_counts(visible, position, site, geometry, .08)
            if any(hits.values()):
                collisions.append({'fraction': float(fraction), 'public_scene': hits})
                break
        detail = {'pose': view, 'collision': collisions}
        evidence['views'].append(detail)
        if collisions:
            detail['rejected'] = 'measured_scene_intersects_observation_hand_sweep'
            continue
        result = servo_grasp_pose(executor.p, view['xyz'], view['body_quat_xyzw'], gripper=-1., max_steps=150)
        executor.motion_evidence.append({**result, 'analytic_stage': 'box_oblique_measurement'})
        detail['motion'] = result
        if executor.p.env.terminated or executor.p.env.truncated:
            detail['rejected'] = 'native_environment_ended'
            break
        if result['final_dist_m'] > .015 or result['final_orientation_err_rad'] > .08:
            detail['rejected'] = 'observation_pose_not_reached'
            executor.capture()
            continue
        detail['identity'] = refresh_grasp_target(executor, before, executor.p._last_obs_eef_pos.copy())
        current = executor.scene.entities.get(before.id)
        if current is None or not current.visible:
            detail['rejected'] = 'stationary_box_not_measured'
            continue
        points = np.asarray(executor.scene.measurement_clouds[before.id])
        clouds.append(points)
        observations.append({'source_step': current.source_step, 'points': len(points),
                             'cameras': sorted(executor.scene.measurement_clouds_by_view.get(before.id, {}))})
    union = np.concatenate(clouds)
    lower, upper = np.quantile(union, (.02, .98), axis=0)
    measured = replace(before, xyz=tuple(np.median(union, axis=0)), lower=tuple(lower),
                       upper=tuple(upper), visible=True, source_step=observations[-1]['source_step'],
                       geometry='stationary_precontact_multiframe_rgbd')
    executor.scene.entities[before.id] = measured
    executor.scene.measurement_clouds[before.id] = union
    evidence.update(observations=observations, fused_stationary_points=len(union),
                    all_observations_precontact=True)
    receipt['geometric_active_views'] = evidence
    return measured
