# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""One public, mesh-swept approach route for all parallel-jaw grasps."""
import math

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

VERSION = 'public-full-route-grasp/8-band-seeds-dev'


def separate_target_points(target_points, scene_points):
    """Remove measured target pixels before downsampling the scene.

    Both clouds come from the same world-coordinate RGB-D arrays. A nearby
    table or neighbour is not a target pixel: a 6 mm nearest-neighbour carve
    would erase real obstacles, and voxelising first can merge the two.
    The 1 micrometre tolerance handles numeric representation only.
    """
    from robots.libero.v5_geometric_grasp import _voxel
    target, scene = map(lambda x: np.asarray(x, dtype=float), (target_points, scene_points))
    target = target[np.isfinite(target).all(axis=1) & (np.linalg.norm(target, axis=1)>1e-6)]
    scene = scene[np.isfinite(scene).all(axis=1) & (np.linalg.norm(scene, axis=1)>1e-6)]
    membership = np.zeros(len(scene), dtype=bool)
    if len(target):
        # Points outside the target AABB cannot be exact instance members.
        # Avoid an expensive nearest search over every distant wall pixel.
        near = ((scene >= target.min(axis=0)-1e-6)
                & (scene <= target.max(axis=0)+1e-6)).all(axis=1)
        # This asks only whether an identical measured pixel exists. An
        # unbounded nearest search on a dense planar target can spend seconds
        # proving the nearest *non-member* is many metres away.
        distance = cKDTree(target).query(scene[near],
            distance_upper_bound=np.nextafter(1e-6, np.inf))[0]
        membership[near] = distance <= 1e-6
    return _voxel(target, .002), _voxel(scene[~membership])


def sample_unified_grasps(target_points, scene_points, name, eef_xyz, body_quat, geometry,
                          pose_screen, height, *, candidate_only=False, include_band_seeds=False):
    """All categories share opposition, sweep/IK screening and ranking."""
    from robots.libero.v5_geometric_grasp import _opposition, side_site_rotation
    from robots.libero.v5_grasp_geometry import (
        measured_band_seeds,
        measured_grasp_regions,
    )
    target, obstacles = separate_target_points(target_points, scene_points)
    region, perception = measured_grasp_regions(target, name)
    if region is None:
        return None, [{'id': 'perception', 'rejected': [perception['reason']], 'perception': perception}]
    obstacle_tree = cKDTree(obstacles) if len(obstacles) else None
    pads = [b for b in geometry['boxes'] if b['name'].endswith('_pad')]
    if len(pads) != 2 or (pose_screen is None and not candidate_only):
        raise ValueError('two measured finger pads and public IK screen required')
    pad_centre = np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in pads], axis=0)
    distal_contact = pad_centre.copy()
    distal_contact[2] = min(b['upper'][2] for b in pads)-.002
    pad_contacts = [('', pad_centre)]
    if distal_contact[2] > pad_centre[2]:
        pad_contacts.append(('_distal_pad', distal_contact))
        edge_contact = pad_centre.copy()
        # Centre a 2mm contact cell wholly inside both distal pad faces.
        # This remains a measured pad placement, subject to the same sweep.
        edge_contact[2] = min(b['upper'][2] for b in pads)-.001
        pad_contacts.append(('_distal_pad_edge_cell', edge_contact))
    base_axis = math.atan2(*region['closing_axis_xy'][::-1])
    records = []
    def seeds():
        yield from region['seeds']
        # Preserve the existing catalogue when it has any measured grasp.
        # Otherwise sample lower side contours; never relax opposition or
        # remove obstacles to turn an unmeasured contact into an option.
        if include_band_seeds or not any(not row['rejected'] for row in records):
            yield from measured_band_seeds(region['points'])

    for seed_index, seed in enumerate(seeds()):
        for axis_index, offset in enumerate((0., math.pi/4, -math.pi/4, math.pi/2)):
            angle = base_axis+offset
            closing = np.array([math.cos(angle), math.sin(angle), 0.])
            centre, fit = _opposition(region['points'], seed, closing)
            if centre is None:
                records.append({'id': f's{seed_index}_a{axis_index}', 'rejected': [fit['reason']], **fit})
                continue
            tangent = np.array([-closing[1], closing[0], 0.])
            approaches = [('top', np.array([0., 0., -1.]))]
            for sign in (-1, 1):
                approaches += [(f'side_{sign}', sign*tangent),
                               (f'oblique_{sign}', (sign*tangent+np.array([0., 0., -1.]))/math.sqrt(2))]
            for approach, direction in approaches:
                site = side_site_rotation(closing, direction)
                body = site @ Rotation.from_euler('z', math.pi/2).as_matrix()
                for suffix, pad_contact in pad_contacts:
                    # A low measured flank can meet the distal pad without
                    # centring the longer finger body through its support.
                    # Both placements retain the same observed flank patches
                    # and undergo the full route and closure collision tests.
                    contact = centre-site@pad_contact
                    pregrasp = contact-direction*.15
                    route = approach_route(eef_xyz, body_quat, contact, Rotation.from_matrix(body).as_quat(),
                                           approach, pregrasp, max(height, region['top_z']+.15))
                    clearance = min(float(obstacle_tree.query(contact)[0]), .2) if obstacle_tree else .2
                    confidence = min(fit['normal_quality'])*min(1., min(fit['normal_patch_support_counts'])/8)
                    row = {'id':f's{seed_index}_a{axis_index}_{approach}'+suffix, 'source':'perception',
                           'rejected':[], 'approach':approach, 'xyz':contact.tolist(),
                           'body_quat_xyzw':Rotation.from_matrix(body).as_quat().tolist(),
                           'closing_axis_xy':closing[:2].tolist(), 'approach_xyz':pregrasp.tolist(),
                           'pad_contact_local_xyz_m': pad_contact.tolist(),
                           'route':route, 'clearance_m':clearance, 'measurement_confidence':confidence,
                           'score':clearance/.2+confidence, **fit}
                    records.append(row)
                    if approach != 'top':
                        # A horizontal wrist can be unreachable at the raised
                        # transit height even when its lower pregrasp is reachable.
                        # Screen an alternate route that rotates at that pregrasp;
                        # neither collision nor IK limits are relaxed.
                        records.append({**row, 'id':row['id']+'_orient_at_pregrasp', 'rejected':[],
                            'route':approach_route(eef_xyz,body_quat,contact,Rotation.from_matrix(body).as_quat(),
                                approach,pregrasp,max(height,region['top_z']+.15),orient_at_pregrasp=True)})
    # Checking routes in score order avoids hundreds of expensive numerical
    # IK solves after a higher-ranked feasible candidate is already found.
    # Unscreened candidates are explicitly untested, never marked feasible.
    ordered = sorted(records,key=lambda r:(bool(r['rejected']),-r.get('score',-1),r['id']))
    if candidate_only:
        # The bounded adapter screens its actual smooth curve, instead of
        # executing the historical piecewise servo route. These proposals
        # have not passed either collision or IK screening yet.
        for row in ordered:
            row['route_status'] = 'not_screened'
        return None, ordered
    selected = None
    for row in ordered:
        if row['rejected']:
            continue
        if selected is not None:
            row['route_status'] = 'not_screened_lower_rank'
            continue
        valid, evidence = sweep_route(eef_xyz,body_quat,row['route'],obstacles,target,geometry,pose_screen=pose_screen)
        row.update(route_screen=evidence,route_status='passed' if valid else 'rejected')
        if not valid:
            row['rejected'].append(evidence['reason'])
        else:
            selected = row
    if selected is None:
        return None, ordered
    plan = {'version':VERSION,'valid':True,'xyz':selected['xyz'],
            'closing_axis_xy':selected['closing_axis_xy'], 'body_quat_xyzw':selected['body_quat_xyzw'],
            'measured_top_z':region['top_z'], 'measured_width_m':selected['width_m'], 'lift_m':.10,
            'sampled_approach':selected['approach'], 'approach_xyz':selected['approach_xyz'],
            'chosen_candidate':selected['id'], 'route':selected['route_screen']['execution_waypoints'],
            'route_screen':selected['route_screen'],
            'score':selected['score'], 'perception':perception, 'private_pose_used':False}
    return plan,ordered


def approach_route(eef_xyz, body_quat, contact, contact_quat, approach, pregrasp, height,
                   *, orient_at_pregrasp=False):
    """Build the exact route checked by planning and consumed by execution."""
    start, contact, entry = map(lambda x: np.asarray(x, dtype=float), (eef_xyz, contact, pregrasp))
    safe = max(float(height), float(start[2]), float(entry[2]))
    transit_quat = body_quat if orient_at_pregrasp else contact_quat
    route = [
        {'phase': 'route_raise', 'xyz': [*start[:2], safe], 'body_quat_xyzw': list(body_quat)},
        {'phase': 'route_pregrasp_above', 'xyz': [*entry[:2], safe], 'body_quat_xyzw': list(transit_quat)},
        {'phase': 'route_pregrasp', 'xyz': entry.tolist(), 'body_quat_xyzw': list(transit_quat)},
    ]
    if orient_at_pregrasp:
        route.append({'phase':'route_orient_at_pregrasp','xyz':entry.tolist(),
                      'body_quat_xyzw':list(contact_quat)})
    return [*route, {'phase':'route_contact','xyz':contact.tolist(),
                    'body_quat_xyzw':list(contact_quat)}]


def sweep_route(start_xyz, start_body_quat, route, obstacles, target, geometry, *, pose_screen):
    """Screen swept hand meshes and numerical joint-limited IK along the route.

    Point-cloud coverage and arm-link collision remain explicit limitations.
    Intermediate sweep samples are inflated by their maximum displacement,
    including hand rotation, so a thin obstacle cannot fall between samples.
    """
    from robots.libero.v5_geometric_grasp import collision_counts
    start = np.asarray(start_xyz, dtype=float)
    previous = Rotation.from_quat(start_body_quat)
    evidence, clearances, execution, ik_schedule = [], [], [], []
    scene_tree = cKDTree(obstacles) if len(obstacles) else None
    target_tree = cKDTree(target) if len(target) else None
    radius = max(float(np.linalg.norm(np.maximum(np.abs(box['lower']), np.abs(box['upper']))))
                 for box in geometry['boxes']) + .04

    def local_counts(points, tree, position, site, opening, margin):
        # The sphere contains every translated, inflated mesh AABB. This
        # culls only distant points and preserves the exact collision test.
        nearby = points[tree.query_ball_point(position, radius + math.sqrt(3)*margin)] if tree else points
        return collision_counts(nearby, position, site, geometry, opening, clearance_m=margin)
    for waypoint in route:
        end = np.asarray(waypoint['xyz'], dtype=float)
        desired = Rotation.from_quat(waypoint['body_quat_xyzw'])
        distance = float(np.linalg.norm(end-start))
        angle = float((desired*previous.inv()).magnitude())
        n = max(1, math.ceil(distance/.006), math.ceil(radius*angle/.006))
        interpolation = Slerp([0., 1.], Rotation.from_matrix([previous.as_matrix(), desired.as_matrix()]))
        inflate = .002 + (distance + radius*angle)/(2*n)
        result = {'phase': waypoint['phase'], 'sweep_samples': n+1,
                  'mesh_inflation_m': inflate, 'collision': None, 'ik_checks': [],
                  'source': 'public_scene_rgbd_static_gripper_mesh_and_proprioception'}
        last_ik_fraction = -1.
        for fraction in np.linspace(0., 1., n+1):
            position = start + fraction*(end-start)
            body = interpolation(float(fraction))
            site = body.as_matrix() @ Rotation.from_euler('z', -math.pi/2).as_matrix()
            external = local_counts(obstacles, scene_tree, position, site, .08, inflate)
            own = local_counts(target, target_tree, position, site, .08, inflate)
            if any(external.values()) or any(own.values()):
                result['collision'] = {'fraction': float(fraction), 'scene': external, 'target': own,
                                       'xyz': position.tolist()}
                evidence.append(result)
                return False, {'version': VERSION, 'reason': 'approach_sweep_collision', 'segments': evidence}
            if scene_tree is not None:
                clearances.append(float(scene_tree.query(position)[0]))
            # Screen orientation as well as translation, including intermediate
            # waypoints; a reachable endpoint does not imply a reachable route.
            if (last_ik_fraction < 0 or fraction == 1 or
                    (fraction-last_ik_fraction)*max(distance, radius*angle) >= .02):
                ik_schedule.append((result, float(fraction), {'phase': waypoint['phase']+f'_{len(ik_schedule)}',
                                  'xyz': position.tolist(), 'body_quat_xyzw': body.as_quat().tolist(),
                                  'contact_endpoint': bool(waypoint['phase']=='route_contact' and fraction==1)}))
                last_ik_fraction = float(fraction)
        evidence.append(result)
        start, previous = end, desired
    # Fingers may intentionally touch the target during closing. Other scene
    # geometry and the palm must remain clear throughout that closing sweep.
    final = route[-1]
    site = Rotation.from_quat(final['body_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -math.pi/2).as_matrix()
    for opening in np.linspace(.08, 0., 9):
        external = local_counts(obstacles, scene_tree, final['xyz'], site, opening, .002)
        own = local_counts(target, target_tree, final['xyz'], site, opening, .002)
        palm = {name: count for name, count in own.items() if 'hand' in name or 'palm' in name}
        if any(external.values()) or any(palm.values()):
            return False, {'version': VERSION, 'reason': 'closure_sweep_collision', 'segments': evidence,
                           'closure': {'opening_m': float(opening), 'scene': external, 'target_palm': palm}}
    # Both screens are mandatory. Reject routes blocked at their last
    # centimetre before spending minutes solving earlier numerical IK poses.
    for segment, fraction, waypoint in ik_schedule:
        ik = pose_screen.check(waypoint['xyz'], waypoint['body_quat_xyzw'])
        segment['ik_checks'].append({'fraction': fraction, **ik})
        if not ik['solution_found']:
            return False, {'version': VERSION, 'reason': 'approach_route_ik_not_found',
                           'segments': evidence}
        execution.append(waypoint)
    return True, {'version': VERSION, 'segments': evidence,
                  'execution_waypoints': execution,
                  'clearance_m': min(clearances, default=.2),
                  'closure_sweep_checked': True, 'arm_link_collisions_checked': False,
                  'screen_order': 'whole_route_and_closure_collision_then_all_scheduled_ik',
                  'unseen_geometry_certified': False}
