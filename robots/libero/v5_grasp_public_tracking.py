# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Reobserve a grasped target near its publicly measured closing pose."""

import base64
import copy
from dataclasses import replace
from itertools import product

import numpy as np

from robots.libero.v5_perception_geometry import measured_points, measured_prompt_pixel, refinement_mask_matches
from rpent.robots.components.sam3_client import Sam3Client

VERSION = 'public-closure-rgbd-target-tracking/2-stationary-negative-dev'


def evaluate_opposed_pad_window(frames):
    """Require current target surface evidence at both inward pad faces.

    Co-motion alone permits a body balanced on one finger. Occluded contact
    remains unmeasured rather than becoming a positive grasp. This public
    geometry gate does not substitute for private contact truth.
    """
    rows=[]
    for frame in frames:
        measured=(frame.get('public_finger_pad_regions') or {}).get('per_view',{})
        supported={}
        for camera,view in measured.items():
            if view.get('current_target_points') is not True:
                continue
            for pad in view.get('pads',[]):
                if pad.get('points_near_inward_face',0)>0:
                    supported.setdefault(pad['geom_name'],[]).append(camera)
        # Main and wrist cameras are synchronized for this capture. Their
        # union is the public observation for the frame; requiring one camera
        # to see both pads rejects valid grasps when the object occludes one
        # side in each view. The union still requires both named inward faces
        # and is evaluated again on a later frame.
        rows.append({'capture_eef_xyz':frame.get('eef_xyz'),
                     'measured_pad_support':supported,
                     'both_pads_observed':len(supported)==2,
                     'fusion_version':'rgbd_dual_view/1',
                     'fused_cameras':sorted(measured)})
    verified=True if len(rows)>=2 and all(r['both_pads_observed'] for r in rows) else None
    return {'version':'public-opposed-pad-window/1-dev','verified':verified,'frames':rows,
            'source':'fresh_target_rgbd_and_public_finger_pose',
            'reason':'both_inward_faces_observed' if verified else 'opposed_contact_unmeasured',
            'private_contact_used':False}


def measure_finger_pad_regions(frame, measured_points_by_view, geometry, finger_qpos):
    """Measure target surface distance to each pad from public inputs only.

    An object box can overlap the jaws while a handle rests on a finger's
    outer mesh. Preserve actual target points and signed independent finger
    positions for diagnosing that ambiguity. No point-count threshold or
    positive grasp verdict is inferred from this measurement.
    """
    from scipy.spatial.transform import Rotation

    pads = geometry.get('finger_pads', [])
    qpos = np.asarray(finger_qpos, dtype=float)
    if len(pads) != 2 or qpos.shape != (2,) or not np.isfinite(qpos).all():
        raise ValueError('two calibrated finger pads and measured joint positions required')
    rotation = (Rotation.from_quat(frame['body_quat_xyzw']).as_matrix()
                @ np.asarray(geometry['rotation_body_to_site']))
    origin = np.asarray(frame['eef_xyz'], dtype=float)
    tolerance = frame.get('opening_calibration_tolerance_m')
    if tolerance is None or not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError('original measured opening tolerance required')
    centres = [np.asarray(pad['neutral_centre_site_m']) + q * np.asarray(pad['joint_axis_site'])
               for pad, q in zip(pads, qpos)]
    halves = [np.asarray(pad['half_size_site_m']) for pad in pads]
    evidence = {}
    for camera, view in frame['per_view'].items():
        measurement = view.get('measurement') or {}
        cloud = (measured_points_by_view or {}).get(camera) or {}
        current = (view.get('current_measurement') is True and cloud.get('src') == 'perception'
                   and cloud.get('object_id') == measurement.get('id')
                   and cloud.get('source_step') == measurement.get('source_step'))
        result = {'current_target_points': bool(current), 'pads': []}
        if current:
            world = np.asarray(cloud['xyz_world'], dtype=float)
            if world.ndim != 2 or world.shape[1:] != (3,) or not np.isfinite(world).all():
                raise ValueError('finite current target Nx3 points required')
            local = (world - origin) @ rotation
            for pad, centre, half in zip(pads, centres, halves):
                distance = np.linalg.norm(np.maximum(np.abs(local - centre) - half, 0.), axis=1)
                # A box also includes the pad's outer and end faces. Keep the
                # inward face separate; proximity to another face cannot
                # establish opposed contact from RGB-D alone.
                inner_sign = -np.sign(centre[0])
                inner_x = centre[0] + inner_sign * half[0]
                face_delta = np.maximum(np.abs(local[:, 1:] - centre[1:]) - half[1:], 0.)
                face_distance = np.sqrt((local[:, 0] - inner_x) ** 2
                                        + np.sum(face_delta ** 2, axis=1))
                inside = np.all(np.abs(local - centre) < half - tolerance, axis=1)
                result['pads'].append({'geom_name': pad['geom_name'],
                    'centre_site_m': centre.tolist(), 'half_size_site_m': half.tolist(),
                    'target_surface_min_distance_m': float(distance.min()) if len(distance) else None,
                    'target_surface_distance_quantiles_m': np.quantile(distance, [.01, .05, .5]).tolist()
                        if len(distance) else None,
                    'points_within_measured_tolerance': int(np.count_nonzero(distance <= tolerance)),
                    'inward_face_x_site_m': float(inner_x),
                    'target_surface_min_inward_face_distance_m': float(face_distance.min()) if len(distance) else None,
                    'points_near_inward_face': int(np.count_nonzero(face_distance <= tolerance)),
                    'target_points_deep_inside_pad_box': int(np.count_nonzero(inside)),
                    'inward_face_contact_inferred': False})
            result['target_point_count'] = len(local)
        evidence[camera] = result
    return {'version': 'public-target-to-two-pad-rgbd/2-inward-face-measurement-dev',
            'source': 'fresh_target_rgbd_and_robot_proprioception',
            'finger_joint_qpos_m': qpos.tolist(), 'association_tolerance_m': float(tolerance),
            'static_geometry_source': geometry['xml'], 'per_view': evidence,
            'positive_grasp_inferred': False, 'private_pose_or_contact_used': False}


def evaluate_tracked_coupling(first, second, interval_s, *, opening_calibration=None,
                             require_coupled_motion=False):
    """Use measured body motion when the fingers hide the contact surface.

    A visible-surface box outside the pads cannot exclude occluded contact.
    It becomes unknown, never positive, until a second fresh measurement
    follows an actual robot translation. Empty aperture, missing lift, stale
    identity and support failures remain failures.
    """
    from robots.libero.v5_grasp_measurement import evaluate_coupled_lift_pair

    frames = copy.deepcopy([first, second])
    for frame in frames:
        for view in frame['per_view'].values():
            conditions = view.get('conditions', {})
            if (view.get('current_measurement')
                    and view.get('finger_geometry', {}).get('mode') == 'calibrated_finger_frame'
                    and conditions.get('near_measured_fingers') is False
                    and all(value is True for name, value in conditions.items()
                            if name != 'near_measured_fingers')):
                conditions['near_measured_fingers'] = None
                view.update(verified=None, reason='visible_surface_does_not_measure_hidden_contact')
    result = evaluate_coupled_lift_pair(*frames, interval_s, maximum_residual_m=.01)
    if require_coupled_motion:
        evidence = result['coupled_lift_evidence']
        measured = []
        for view in evidence['per_view'].values():
            if (view['fresh_same_body'] and view['robot_translation_m'] >= evidence['minimum_translation_m']
                    and view['robot_rotation_degrees'] is not None
                    and view['robot_rotation_degrees'] <= evidence['maximum_rotation_degrees']):
                measured.append(view['coupling_measured'])
        verdicts = set(measured)
        coupled = next(iter(verdicts)) if len(verdicts) == 1 else None
        result['required_coupled_motion'] = {
            'version': 'public-all-positive-grasp-coupling/1-dev',
            'verified': coupled, 'measured_views': len(measured),
            'reason': ('fresh_views_disagree' if len(verdicts) > 1 else
                       'measured_body_robot_motion' if measured else 'motion_or_target_unmeasured')}
        # Bounding-box overlap and aperture supply no exception to measured
        # co-motion. Preserve existing negative evidence and nullable inputs.
        if result['verified'] is not False and coupled is not True:
            result.update(verified=False if coupled is False else None,
                          verification='failed' if coupled is False else 'unmeasured',
                          reason='required_public_coupled_motion_not_verified')
    result['tracking_verifier_version'] = ('public-tracked-body-active-lift/r4-empty-aperture-residual1cm/2'
        if opening_calibration else 'public-tracked-body-active-lift/residual1cm/1')
    if opening_calibration is not None:
        threshold = opening_calibration['closed_empty_max_m'] + opening_calibration['tolerance_m']
        empty = [frame.get('opening_m') is not None and frame['opening_m'] <= threshold for frame in frames]
        result['empty_aperture_evidence'] = {'source': 'robot_proprioception',
            'opening_m': [frame.get('opening_m') for frame in frames],
            'original_empty_closed_upper_m': threshold, 'calibration': opening_calibration,
            'empty_frame': empty}
        # Missing RGB-D cannot invalidate a measured empty closed aperture.
        # A nonempty aperture still supplies no positive hold evidence.
        if any(empty):
            result.update(verified=False, verification='failed',
                          reason='matches_original_calibrated_empty_closed_range')
    return result


def evaluate_public_hold_window(frames, proprioception, *, control_dt_s=.05,
                                opening_calibration=None):
    """Check a physical half-second hold from public sensors only.

    Camera inference time does not advance a paused environment. Use actual
    action counters, and preserve a missing view instead of substituting a
    predicted object pose. This measures public stability, not finger contact.
    """
    from scipy.spatial.transform import Rotation

    evidence = {'version': 'public-rgbd-physical-hold/1-dev', 'verified': None,
                'frames': frames, 'proprioception': proprioception,
                'control_dt_s': control_dt_s, 'duration_s': None, 'per_view': {},
                'private_pose_or_contact_used': False}
    if not frames or not proprioception or opening_calibration is None:
        return {**evidence, 'reason': 'physical_hold_measurements_missing'}
    steps = [row['used_sim_steps'] for row in proprioception]
    duration = (steps[-1] - steps[0]) * control_dt_s
    evidence['duration_s'] = duration
    if (len(frames) < 3 or len(steps) < 11 or duration < .5 - 1e-9
            or any(b - a != 1 for a, b in zip(steps, steps[1:]))):
        return {**evidence, 'reason': 'physical_half_second_hold_incomplete'}
    empty_max = opening_calibration['closed_empty_max_m'] + opening_calibration['tolerance_m']
    if any(row['opening_m'] <= empty_max for row in proprioception):
        return {**evidence, 'verified': False, 'reason': 'empty_aperture_during_physical_hold'}
    verdicts = set()
    cameras = set.intersection(*(set(frame['per_view']) for frame in frames))
    for camera in sorted(cameras):
        views = [frame['per_view'][camera] for frame in frames]
        objects = [view.get('measurement') for view in views]
        fresh = (all(view.get('current_measurement') for view in views)
                 and all(objects)
                 and all(obj.get('src') == 'perception' and obj.get('visible') for obj in objects)
                 and len({(obj['id'], obj['name']) for obj in objects}) == 1
                 and all(b['source_step'] > a['source_step'] for a, b in zip(objects, objects[1:])))
        detail = {'fresh_same_body': bool(fresh), 'verified': None}
        if fresh:
            conditions = [value for view in views for key, value in view.get('conditions', {}).items()
                          if key != 'near_measured_fingers']
            relative = [Rotation.from_quat(frame['body_quat_xyzw']).inv().apply(
                np.asarray(obj['xyz']) - frame['eef_xyz']) for frame, obj in zip(frames, objects)]
            residual = max(float(np.linalg.norm(value - relative[0])) for value in relative)
            detail['maximum_public_body_tcp_displacement_m'] = residual
            verdict = (False if residual > .01 or any(value is False for value in conditions)
                       else None if any(value is None for value in conditions) else True)
            detail['verified'] = verdict
            if verdict is not None:
                verdicts.add(verdict)
        evidence['per_view'][camera] = detail
    verdict = next(iter(verdicts)) if len(verdicts) == 1 else None
    return {**evidence, 'verified': verdict,
            'reason': ('physical_hold_views_disagree' if len(verdicts) > 1 else
                       'public_body_stable_during_physical_hold' if verdict is True else
                       'public_hold_failed' if verdict is False else 'physical_hold_body_unmeasured')}


def translated_hint(before, closing_eef_xyz, current_eef_xyz):
    """A translation hint is never itself a current target measurement.

    The analytic lift keeps wrist orientation fixed. This hint uses only its
    measured pre-contact bounds and public robot displacement; the RGB-D
    mask must independently match it before entering the perception cache.
    """
    delta = np.asarray(current_eef_xyz, dtype=float) - np.asarray(closing_eef_xyz, dtype=float)
    if delta.shape != (3,) or not np.isfinite(delta).all():
        raise ValueError('finite public EEF translation required')
    return replace(before, xyz=tuple(np.asarray(before.xyz) + delta),
                   lower=tuple(np.asarray(before.lower) + delta),
                   upper=tuple(np.asarray(before.upper) + delta),
                   geometry='public_robot_translation_hint_not_measurement')


def pose_hint(before, closing_eef_xyz, current_eef_xyz, closing_quat, current_quat):
    """Rotate a query envelope using public wrist poses, never a target pose.

    Contact policies can rotate after the lowest pick pose. A world-axis
    translation of the old bounds then searches the wrong region. This is
    still only a segmentation hint; a fresh RGB-D mask must match it.
    """
    from scipy.spatial.transform import Rotation

    quats = [np.asarray(q, dtype=float) for q in (closing_quat, current_quat)]
    if any(q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) <= 1e-9
           for q in quats):
        raise ValueError('two measured finite wrist quaternions required')
    start, end = [np.asarray(p, dtype=float) for p in (closing_eef_xyz, current_eef_xyz)]
    if any(p.shape != (3,) or not np.isfinite(p).all() for p in (start, end)):
        raise ValueError('two measured finite EEF positions required')
    transform = Rotation.from_quat(quats[1]).as_matrix() @ Rotation.from_quat(quats[0]).as_matrix().T
    corners = np.asarray(list(product(*zip(before.lower, before.upper))))
    corners = (corners - start) @ transform.T + end
    xyz = transform @ (np.asarray(before.xyz) - start) + end
    return replace(before, xyz=tuple(xyz), lower=tuple(corners.min(axis=0)),
                   upper=tuple(corners.max(axis=0)),
                   geometry='public_robot_pose_hint_not_measurement')


def matching_cloud(world, mask, hint, *, clean=False, complete_boundary=False):
    if mask is None or mask.shape != world.shape[:2]:
        return None
    if clean:
        from robots.libero.v5_grasp_geometry import clean_object_mask
        mask, _ = clean_object_mask(world, mask, prior_lower=hint.lower, prior_upper=hint.upper)
    if complete_boundary:
        from robots.libero.v5_grasp_geometry import complete_instance_boundary, complete_planar_boundary
        mask, _ = complete_instance_boundary(world, mask)
        mask, _ = complete_planar_boundary(world, mask)
    points = measured_points(world, mask)
    return points if refinement_mask_matches(points, hint.lower, hint.upper) else None


def stationary_source_is_unique(scene, before):
    """Known peers forbid rebinding a missing moving target at its old place."""
    peers = [entity for entity in scene.entities.values()
             if entity.name == before.name and not getattr(entity, 'part_of', None)]
    return len(peers) == 1 and peers[0].id == before.id


def refresh_grasp_target(executor, before, closing_eef_xyz):
    """Reject distant same-category masks, then try a current-depth point hint."""
    from robots.libero.v5_runtime import segmentation_prompt

    executor.capture()
    state, scene = executor.toolkit._state, executor.scene
    matched_masks = {}
    def current_cloud(world, mask, hint):
        points = matching_cloud(world, mask, hint,
            clean=getattr(executor, 'analytic_geometry_v1', False),
            complete_boundary=getattr(executor, 'unified_grasp_route_v1', False))
        if points is not None and getattr(scene, 'record_sam_masks_v6', False):
            matched_masks.setdefault(camera, []).append(scene.save_sam_mask(mask, camera))
        return points
    hint = translated_hint(before, closing_eef_xyz, executor.p._last_obs_eef_pos)
    closing_quat = getattr(executor, 'grasp_public_closing_quat', None)
    hint_source = 'precontact_measured_bounds_and_public_robot_translation'
    if closing_quat is not None:
        current_quat = executor.p.env.raw_obs()['robot0_eef_quat']
        hint = pose_hint(before, closing_eef_xyz, executor.p._last_obs_eef_pos,
                         closing_quat, current_quat)
        hint_source = 'precontact_measured_bounds_and_public_robot_pose'
    clouds, evidence, worlds = {}, {}, {}
    stationary_query_allowed = stationary_source_is_unique(scene, before)
    for camera in ('agentview', 'wrist'):
        world = state.load(f'{camera}_world_high.npz')
        worlds[camera] = world
        image = base64.b64encode(state.load_bytes(f'{camera}_high.png')).decode('ascii')
        reply = scene.rpc.call('sam3.segment_all', kwargs={'image_base64': image,
            'text_prompt': segmentation_prompt(before.name), 'min_score': .35}, timeout_s=120)
        scene.calls += 1
        instances = reply.get('instances', [])
        matched = []
        for item in instances:
            points = current_cloud(world, Sam3Client._decode_result(item).mask, hint)
            if points is not None:
                matched.append(points)
        mode, point = 'named_mask_in_public_motion_envelope', None
        if not matched:
            point = measured_prompt_pixel(world, hint.lower, hint.upper)
            if point is not None:
                guided = scene.rpc.call('sam3.segment', kwargs={'image_base64': image,
                    'point': point, 'min_score': .5}, timeout_s=120)
                scene.calls += 1
                if guided.get('found'):
                    points = current_cloud(world, Sam3Client._decode_result(guided).mask, hint)
                    if points is not None:
                        matched.append(points)
                        mode = 'current_rgbd_point_in_public_motion_envelope'
        # A failed pick can leave the sole known source on its support. The
        # moving query must not erase that fresh negative evidence. This old
        # envelope only guides segmentation; evaluate_grasp_frame still
        # measures lift and active robot/object coupling from the new cloud.
        if not matched and stationary_query_allowed:
            stationary = []
            for item in instances:
                points = current_cloud(world, Sam3Client._decode_result(item).mask, before)
                if points is not None:
                    stationary.append(points)
            if not stationary:
                point = measured_prompt_pixel(world, before.lower, before.upper)
                if point is not None:
                    guided = scene.rpc.call('sam3.segment', kwargs={'image_base64': image,
                        'point': point, 'min_score': .5}, timeout_s=120)
                    scene.calls += 1
                    if guided.get('found'):
                        points = current_cloud(world, Sam3Client._decode_result(guided).mask, before)
                        if points is not None:
                            stationary.append(points)
            if len(stationary) == 1:
                matched = stationary
                mode = 'fresh_rgbd_at_unique_precontact_source_envelope'
        if len(matched) == 1:
            clouds[camera] = matched[0]
        evidence[camera] = {'matching_masks': len(matched), 'used': len(matched) == 1,
                            'method': mode, 'point': point,
                            'stationary_query_allowed': stationary_query_allowed}
    if getattr(executor, 'unified_grasp_route_v1', False) and len(clouds) == 2:
        from scipy.spatial import cKDTree
        from robots.libero.v5_grasp_geometry import complete_crossview_boundary

        masks = {}
        for camera, points in clouds.items():
            world = worlds[camera]
            flat = world.reshape(-1, 3)
            near = ((flat >= points.min(axis=0)-1e-6)
                    & (flat <= points.max(axis=0)+1e-6)).all(axis=1)
            mask = np.zeros(len(flat), bool)
            mask[near] = cKDTree(points).query(flat[near])[0] <= 1e-6
            masks[camera] = mask.reshape(world.shape[:2])
        # Both associations use the original current masks, so one completion
        # cannot recursively invent support for the other view.
        for camera, other in (('agentview', 'wrist'), ('wrist', 'agentview')):
            mask, detail = complete_crossview_boundary(worlds[camera], masks[camera],
                worlds[other], masks[other], state.load(f'{other}_metadata.json'))
            clouds[camera] = measured_points(worlds[camera], mask)
            evidence[camera]['crossview_boundary'] = detail
    if clouds:
        points = np.concatenate(list(clouds.values()))
        lower, upper = np.quantile(points, (.02, .98), axis=0)
        measured = replace(before, xyz=tuple(np.median(points, axis=0)),
            lower=tuple(lower), upper=tuple(upper), visible=True,
            source_step=state.latest_step, geometry=None)
        scene.entities[before.id] = measured
        scene.measurement_clouds[before.id] = points
        scene.cache_independent_views(measured, clouds)
    else:
        scene.entities[before.id] = replace(before, visible=False)
        scene.measurement_views[before.id] = {}
        scene.measurement_clouds_by_view[before.id] = {}
    return {'version': VERSION, 'source': 'perception', 'source_step': state.latest_step,
        'hint_source': hint_source,
        'hint_is_measurement': False, 'views': evidence, 'matched_sam_mask_files': matched_masks,
        'private_pose_used': False,
        **({'instance_boundary_version':'public-depth-continuous-instance-boundary/1-dev'}
           if getattr(executor, 'unified_grasp_route_v1', False) else {})}
