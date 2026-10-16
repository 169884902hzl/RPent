# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Geometric parallel-jaw sampling with public scene-point collision checks.

Uses the installed Panda collision-mesh convex hulls and a box broad phase.
It checks the open-hand approach and closed-hand lift against observed points;
unseen geometry and arm-link collision are not certified by this test.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import numpy as np

VERSION = 'public-geometric-grasp/6-contact-dev'


def stl_vertices(path):
    """Read robot geometry; no simulation scene state is accessed."""
    data = Path(path).read_bytes()
    count = struct.unpack_from('<I', data, 80)[0] if len(data) >= 84 else -1
    if count >= 0 and len(data) == 84 + count * 50:
        dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
        return np.frombuffer(data, dtype=dtype, offset=84)['vertices'].reshape(-1, 3).astype(float)
    values = [line.split()[1:] for line in data.decode('ascii').splitlines()
              if line.strip().startswith('vertex ')]
    if not values:
        raise ValueError('STL contains no robot vertices')
    return np.asarray(values, dtype=float)


def _vector(element, field, default):
    return np.asarray(element.get(field, default).split(), dtype=float)


def _rotation(element):
    from scipy.spatial.transform import Rotation
    w, x, y, z = _vector(element, 'quat', '1 0 0 0')
    return Rotation.from_quat([x, y, z, w]).as_matrix()


@lru_cache(maxsize=2)
def panda_geometry(xml_path):
    """Resolve actual hand, finger and pad bounds in the public grip-site frame."""
    from scipy.spatial import ConvexHull

    xml_path = Path(xml_path)
    root = ET.fromstring(xml_path.read_bytes())
    meshes = {e.get('name'): xml_path.parent / e.get('file') for e in root.findall('asset/mesh')}
    hand = root.find(".//body[@name='right_gripper']")
    site = hand.find("body[@name='eef']/site[@name='grip_site']")
    site_offset = _vector(hand.find("body[@name='eef']"), 'pos', '0 0 0') + _vector(site, 'pos', '0 0 0')
    boxes = []
    references = [{'path': str(xml_path), 'sha256': hashlib.sha256(xml_path.read_bytes()).hexdigest()}]
    palm = hand.find("geom[@name='hand_collision']")
    path = meshes[palm.get('mesh')]
    vertices = stl_vertices(path) @ _rotation(palm).T + _vector(palm, 'pos', '0 0 0') - site_offset
    boxes.append({'name': 'palm', 'lower': vertices.min(axis=0).tolist(), 'upper': vertices.max(axis=0).tolist(),
                  'convex_halfspaces': ConvexHull(vertices).equations.tolist()})
    references.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for body_name, sign in (('leftfinger', 1), ('rightfinger', -1)):
        body = hand.find("body[@name='" + body_name + "']")
        rotation = _rotation(body)
        position = _vector(body, 'pos', '0 0 0') - site_offset
        joint_axis = _vector(body.find('joint'), 'axis', '0 1 0')
        slide = rotation @ joint_axis * sign  # metres per half-aperture
        geom = next(g for g in body.findall('geom') if g.get('name', '').endswith('_collision'))
        path = meshes[geom.get('mesh')]
        vertices = (stl_vertices(path) @ _rotation(geom).T + _vector(geom, 'pos', '0 0 0')) @ rotation.T + position
        boxes.append({'name': body_name, 'lower': vertices.min(axis=0).tolist(),
                      'upper': vertices.max(axis=0).tolist(), 'slide_per_half_opening': slide.tolist(),
                      'convex_halfspaces': ConvexHull(vertices).equations.tolist()})
        if not any(r['path'] == str(path) for r in references):
            references.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        tip = body.find('body')
        pad = tip.find('geom')
        half = _vector(pad, 'size', '0 0 0')
        corners = np.asarray([(x, y, z) for x in (-half[0], half[0])
                              for y in (-half[1], half[1]) for z in (-half[2], half[2])])
        vertices = ((corners @ _rotation(pad).T + _vector(pad, 'pos', '0 0 0')) @ _rotation(tip).T
                    + _vector(tip, 'pos', '0 0 0')) @ rotation.T + position
        boxes.append({'name': body_name + '_pad', 'lower': vertices.min(axis=0).tolist(),
                      'upper': vertices.max(axis=0).tolist(), 'slide_per_half_opening': slide.tolist(),
                      'convex_halfspaces': ConvexHull(vertices).equations.tolist()})
    return {'version': VERSION, 'source': 'robot_description', 'boxes': boxes, 'references': references,
            'site_offset_in_gripper_m': site_offset.tolist(), 'max_opening_m': .08,
            'collision_model': 'actual_collision_mesh_convex_hulls_with_axis_aligned_broad_phase_in_grip_site'}


def site_rotation(yaw):
    from scipy.spatial.transform import Rotation
    body = Rotation.from_euler('z', yaw).as_matrix() @ Rotation.from_euler('x', math.pi).as_matrix()
    return body @ Rotation.from_euler('z', -math.pi/2).as_matrix()


def side_site_rotation(closing, approach):
    """Orient actual fingers horizontally, with closure across the measured flanks."""
    closing, approach = np.array(closing, dtype=float, copy=True), np.array(approach, dtype=float, copy=True)
    closing /= np.linalg.norm(closing)
    approach /= np.linalg.norm(approach)
    if abs(closing @ approach) > 1e-6:
        raise ValueError('closing and finger approach must be perpendicular')
    return np.c_[closing, np.cross(approach, closing), approach]


def servo_grasp_pose(policy, xyz, body_quat_xyzw, *, gripper=-1., max_steps=150,
                     tol=.008, ori_tol=.05, trace_steps=False, motion_diagnostic=None):
    """Public full-pose OSC servo for horizontal approaches; no scene state is read."""
    from scipy.spatial.transform import Rotation
    target = np.asarray(xyz, dtype=float)
    desired = Rotation.from_quat(body_quat_xyzw)
    trajectory = []
    actions = 0
    for step in range(max_steps):
        current = np.asarray(policy._last_obs_eef_pos, dtype=float)
        rotation = Rotation.from_quat(policy.env.raw_obs()['robot0_eef_quat'])
        delta = target - current
        error = (desired * rotation.inv()).as_rotvec()
        distance, angle = float(np.linalg.norm(delta)), float(np.linalg.norm(error))
        sample = {'step': step, 'eef': current.tolist(), 'dist': distance,
                  'orientation_error_rad': angle}
        if motion_diagnostic is not None:
            sample['contact_and_joints'] = motion_diagnostic()
        trajectory.append(sample)
        if distance < tol and angle < ori_tol:
            break
        action = np.zeros(7, dtype=np.float32)
        action[:3] = np.clip(delta, -.02, .02) / .05
        action[3:6] = error * min(1., .08 / max(angle, 1e-12)) / .50
        action[6] = gripper
        policy._step_env(action)
        actions += 1
        if policy.env.terminated or policy.env.truncated:
            break
    rotation = Rotation.from_quat(policy.env.raw_obs()['robot0_eef_quat'])
    return {'name': 'move_grasp_pose', 'final_eef_pos': np.asarray(policy._last_obs_eef_pos).tolist(),
            'final_dist_m': float(np.linalg.norm(target - policy._last_obs_eef_pos)),
            'final_orientation_err_rad': float((desired * rotation.inv()).magnitude()),
            'target_xyz': target.tolist(), 'target_body_quat_xyzw': list(body_quat_xyzw),
            'steps_used': actions, 'actions_used': actions, 'max_steps': max_steps,
            'terminated': policy.env.terminated, 'truncated': policy.env.truncated,
            **({'trajectory': trajectory, 'last_10_steps': trajectory[-10:],
                'final_contact_and_joints': motion_diagnostic() if motion_diagnostic else None}
               if trace_steps else {})}


def collision_counts(points, xyz, rotation, geometry, opening, *, clearance_m=.002, return_points=False):
    """Count observed points in actual mesh hulls; target contact is checked separately."""
    local = (np.asarray(points) - np.asarray(xyz)) @ rotation
    counts, collision_points = {}, {}
    for box in geometry['boxes']:
        slide = np.asarray(box.get('slide_per_half_opening', [0, 0, 0])) * opening / 2
        lower = np.asarray(box['lower']) + slide - clearance_m
        upper = np.asarray(box['upper']) + slide + clearance_m
        inside = ((local >= lower) & (local <= upper)).all(axis=1)
        if box.get('convex_halfspaces'):
            equations = np.asarray(box['convex_halfspaces'])
            # MuJoCo collides mesh convex hulls. An AABB corner need not be
            # part of the physical hand; use it only as the broad phase.
            supported = (((local[inside] - slide) @ equations[:, :3].T
                          + equations[:, 3]) <= clearance_m).all(axis=1)
            counts[box['name']] = int(supported.sum())
            if return_points:
                collision_points[box['name']] = np.asarray(points)[np.flatnonzero(inside)[supported]][:32].tolist()
        else:
            counts[box['name']] = int(inside.sum())
            if return_points:
                collision_points[box['name']] = np.asarray(points)[inside][:32].tolist()
    return (counts, collision_points) if return_points else counts


def remove_measured_hand(points, eef_xyz, body_quat, geometry, opening):
    """Filter the current hand using proprioception and the pinned robot meshes."""
    from scipy.spatial.transform import Rotation
    body = Rotation.from_quat(body_quat).as_matrix()
    rotation = body @ Rotation.from_euler('z', -math.pi/2).as_matrix()
    local = (np.asarray(points) - np.asarray(eef_xyz)) @ rotation
    occupied = np.zeros(len(local), dtype=bool)
    for box in geometry['boxes']:
        slide = np.asarray(box.get('slide_per_half_opening', [0, 0, 0])) * opening / 2
        lower = np.asarray(box['lower']) + slide - .006
        upper = np.asarray(box['upper']) + slide + .006
        occupied |= ((local >= lower) & (local <= upper)).all(axis=1)
    return np.asarray(points)[~occupied], int(occupied.sum())


def _voxel(points, size=.004):
    points = np.asarray(points, dtype=float)
    points = points[np.isfinite(points).all(axis=1) & (np.linalg.norm(points, axis=1) > 1e-6)]
    _, index = np.unique(np.floor(points / size).astype(int), axis=0, return_index=True)
    return points[np.sort(index)]


def _opposition(points, centre, closing):
    """Measure both flanks and their local surface normals, without learned weights."""
    from scipy.spatial import cKDTree
    tangent = np.array([-closing[1], closing[0], 0.])
    delta = points - centre
    # A rim candidate describes a local patch. The opposite rim of the same
    # bowl can lie on this strip but outside the open jaws; including it
    # incorrectly rejects a narrow local rim as the full bowl diameter.
    band = points[(abs(delta @ tangent) <= .012) & (abs(delta[:, 2]) <= .010)
                  & (abs(delta @ closing) <= .08 / 2)]
    if len(band) < 20:
        return None, {'reason': 'opposing_surfaces_not_measured', 'points': len(band)}
    projection = (band - centre) @ closing
    lower, upper = np.quantile(projection, [.02, .98])
    width = float(upper - lower)
    if width < .004 or width + .008 >= .08:
        return None, {'reason': 'width_outside_gripper_range', 'width_m': width}
    qualities, counts, patch_counts, contact_centres = [], [], [], []
    tree = cKDTree(points)
    for sign, edge in ((-1, lower), (1, upper)):
        flank = band[abs(projection - edge) <= .004]
        counts.append(len(flank))
        if len(flank) < 4:
            return None, {'reason': 'one_flank_unmeasured', 'width_m': width, 'flank_counts': counts}
        # A flank's median can lie between its top and side faces. Its nearest
        # neighbourhood then mixes faces and rejects a real side contact.
        # Measure normals on actual flank pixels, and require a coherent
        # finger-sized patch of opposing normals instead.
        queries = flank[np.linspace(0, len(flank)-1, min(32, len(flank)), dtype=int)]
        distances, neighbours = tree.query(queries, k=min(30, len(points)))
        supporting = []
        for query, ds, ids in zip(queries, distances, neighbours):
            local = points[ids[ds <= .006]]
            if len(local) < 6:
                continue
            values, axes = np.linalg.eigh(np.cov(local.T))
            if values[1] <= 1e-8 or values[0] > .2 * values[1]:
                continue
            normal = axes[:, 0]
            if normal @ (query - centre) < 0:
                normal = -normal
            quality = float(normal @ (sign * closing))
            if quality >= .65:
                supporting.append((query, quality))
        patches = []
        for query, _ in supporting:
            patch = [(point, quality) for point, quality in supporting
                     if np.linalg.norm(point - query) <= .008]
            if len(patch) >= 4:
                patches.append((float(np.mean([quality for _, quality in patch])), len(patch),
                                np.mean([point for point, _ in patch], axis=0)))
        quality, patch_count, contact_centre = max(patches, key=lambda p: (p[0], p[1]),
                                                   default=(0., 0, None))
        qualities.append(quality)
        patch_counts.append(patch_count)
        contact_centres.append(contact_centre)
    if min(qualities) < .65:
        return None, {'reason': 'surface_normals_not_opposed', 'width_m': width, 'normal_quality': qualities,
                      'normal_patch_support_counts': patch_counts}
    # The search-band origin need not lie on the measured flank patches.
    # Centre the pad faces on those patches, then convert to the TCP below.
    centred = np.mean(contact_centres, axis=0)
    width = float((contact_centres[1] - contact_centres[0]) @ closing)
    if width < .004 or width + .008 >= .08:
        return None, {'reason': 'measured_contact_patch_width_outside_gripper_range', 'width_m': width}
    return centred, {'width_m': width, 'normal_quality': qualities, 'flank_counts': counts,
                     'normal_patch_support_counts': patch_counts,
                     'measured_contact_patch_centres_xyz': [point.tolist() for point in contact_centres],
                     'normal_estimator': 'coherent_local_normals_on_actual_flank_points/1-dev',
                     'antipodal_quality': min(qualities)}


def sample_grasps(target_points, scene_points, name, eef_xyz, current_yaw, geometry,
                  *, current_body_quat_xyzw=None, pose_screen=None, approach_height=None):
    """Sample top and lateral entries, rank admissible grasps, retain every rejection."""
    from scipy.spatial import cKDTree
    from robots.libero.v5_analytic_grasp import top_grasp
    target, scene = _voxel(target_points, .002), _voxel(scene_points)
    pads = [box for box in geometry['boxes'] if box['name'].endswith('_pad')]
    if len(pads) != 2:
        raise ValueError('two robot-description finger contact pads required')
    pad_centre_site = np.mean([(np.asarray(box['lower']) + box['upper']) / 2 for box in pads], axis=0)
    baseline = top_grasp(target, name, eef_xyz, current_yaw, connected_handle=True)
    if not baseline.get('valid'):
        return None, [{'id': 'base', 'rejected': [baseline.get('reason')], 'base_plan': baseline}]
    base = np.asarray(baseline['xyz'])
    base_axis = math.atan2(*baseline['closing_axis_xy'][::-1])
    base = base + site_rotation(base_axis + math.pi/2) @ pad_centre_site
    centres = [base]
    if baseline['fit'] == 'measured_rim_patch':
        centre_xy = np.median(target[:, :2], axis=0)
        top = target[target[:, 2] > np.quantile(target[:, 2], .8)]
        for angle in np.linspace(0, 2*math.pi, 8, endpoint=False):
            direction = np.array([math.cos(angle), math.sin(angle)])
            point = top[np.argmax((top[:, :2] - centre_xy) @ direction)]
            centres.append(np.array([*point[:2], base[2]]))
    else:
        tangent = np.array([-math.sin(base_axis), math.cos(base_axis), 0.])
        centres += [base + tangent * offset for offset in (-.015, .015)]
    # Contact depth is also a geometric candidate dimension. The old single
    # depth put the palm into a visible bottle cap, despite valid opposition.
    # Keep that candidate and sample neighbouring pad depths; every pose still
    # passes the same measured opposition and actual-mesh collision checks.
    centres = [centre + np.array([0., 0., dz]) for centre in centres
               for dz in (-.006, 0., .006, .012)]
    # Public target points may be part of the scene cloud; exclude only points
    # close to that measured instance, and test target/palm interference below.
    near_target = cKDTree(target).query(scene, k=1)[0] < .006 if len(scene) else np.zeros(0, dtype=bool)
    obstacles = scene[~near_target]
    records = []
    for centre_index, centre in enumerate(centres):
        for axis_index, offset in enumerate((0., math.pi/4, -math.pi/4, math.pi/2)):
            angle = base_axis + offset
            closing = np.array([math.cos(angle), math.sin(angle), 0.])
            pad_contact, fit = _opposition(target, centre, closing)
            for approach, flip in (('top', False), ('side_left', False), ('side_right', False),
                                   ('side_left', True), ('side_right', True)):
                row = {'id': f'c{centre_index}_a{axis_index}_{approach}' + ('_flip' if flip else ''),
                       'source': 'perception', 'parallel_jaw_flip': flip,
                       'approach': approach, 'closing_axis_xy': closing[:2].tolist(),
                       'rejected': [], **fit}
                records.append(row)
                if pad_contact is None:
                    row['rejected'].append(fit['reason']); continue
                yaw = angle + math.pi/2
                yaw += round((current_yaw - yaw) / math.pi) * math.pi
                rotation = site_rotation(yaw)
                if approach != 'top':
                    tangent = np.array([-closing[1], closing[0], 0.])
                    direction = tangent * (-1 if approach == 'side_left' else 1)
                    rotation = side_site_rotation(-closing if flip else closing, direction)
                contact = pad_contact - rotation @ pad_centre_site
                stage = (contact + np.array([0., 0., .15]) if approach == 'top'
                         else contact - direction * .15)
                from scipy.spatial.transform import Rotation
                body_rotation = rotation @ Rotation.from_euler('z', math.pi/2).as_matrix()
                row.update(xyz=contact.tolist(), yaw=yaw, pitch=0.,
                           public_pad_contact_centre_xyz=pad_contact.tolist(),
                           pad_centre_site_m=pad_centre_site.tolist(),
                           orientation='downward_fingers' if approach == 'top' else 'horizontal_fingers',
                           body_quat_xyzw=Rotation.from_matrix(body_rotation).as_quat().tolist())
                row['approach_xyz'] = stage.tolist()
                collision = []
                for fraction in np.linspace(0, 1, 16):
                    pose = stage + fraction * (contact - stage)
                    hits = collision_counts(obstacles, pose, rotation, geometry, .08)
                    target_hits = collision_counts(target, pose, rotation, geometry, .08)
                    if any(hits.values()) or any(target_hits.values()):
                        collision.append({'fraction': float(fraction), 'scene': hits, 'target': target_hits})
                        break
                for fraction in np.linspace(0, 1, 11):
                    pose = contact + np.array([0., 0., .1 * fraction])
                    hits = collision_counts(obstacles, pose, rotation, geometry, row['width_m'])
                    if any(hits.values()):
                        collision.append({'lift_fraction': float(fraction), 'scene': hits}); break
                if collision:
                    row.update(collision=collision)
                    row['rejected'].append('observed_scene_or_target_intersects_actual_gripper_bounds')
                    continue
                if pose_screen is not None:
                    height = (max(float(eef_xyz[2]), float(baseline['measured_top_z']) + .15)
                              if approach_height is None else float(approach_height))
                    waypoints = ([('orient', np.array([*contact[:2], height])), ('descend', contact)]
                                 if approach == 'top' else
                                 [('side_above', np.array([*stage[:2], height])),
                                  ('side_descend', stage), ('side_contact', contact)])
                    waypoints.append(('lift', contact + np.array([0., 0., .10])))
                    row['pose_screen_checks'] = []
                    for phase, position in waypoints:
                        evidence = pose_screen.check(position.tolist(), row['body_quat_xyzw'])
                        row['pose_screen_checks'].append({'phase': phase, 'target_xyz': position.tolist(),
                                                         **evidence})
                        if not evidence['solution_found']:
                            row['rejected'].append('joint_limited_pose_solution_not_found')
                            break
                    if row['rejected']:
                        continue
                clearance = min(cKDTree(obstacles).query(contact)[0], .2) if len(obstacles) else .2
                orientation_change = (float((Rotation.from_matrix(body_rotation)
                    * Rotation.from_quat(current_body_quat_xyzw).inv()).magnitude())
                    if current_body_quat_xyzw is not None else None)
                motion_cost = 0. if orientation_change is None else .25 * orientation_change / math.pi
                row.update(clearance_m=float(clearance),
                           orientation_change_rad=orientation_change, orientation_motion_cost=motion_cost,
                           score=float(fit['antipodal_quality'] + clearance / .2 - motion_cost),
                           robot_geometry=geometry['references'], collision_model=geometry['collision_model'])
    ordered = sorted(records, key=lambda r: (bool(r['rejected']), -r.get('score', -1), r['id']))
    accepted = [r for r in ordered if not r['rejected']]
    if not accepted:
        return None, ordered
    best = accepted[0]
    plan = {**baseline, 'version': VERSION, 'xyz': best['xyz'], 'yaw': best['yaw'],
            'closing_axis_xy': best['closing_axis_xy'], 'measured_width_m': best['width_m'],
            'sampled_approach': best['approach'], 'approach_xyz': best['approach_xyz'],
            'body_quat_xyzw': best['body_quat_xyzw'], 'orientation': best['orientation'],
            'chosen_candidate': best['id'], 'score': best['score'], 'robot_geometry': geometry['references']}
    return plan, ordered
