# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Mesh sweep and numerical IK for a sampled public RGB-D trajectory."""
from __future__ import annotations

import copy
import json
import math
import itertools

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

from robots.libero.v5_geometric_grasp import collision_counts


def _point_array(points):
    value=np.asarray(points,float)
    return value if value.ndim==2 and value.shape[1]==3 else value.reshape(-1,3)


class PublicRouteScreen:
    """Reuses r9 hulls and IK; certifies only observed hand/payload geometry."""

    # Historical public checkpoints contain static screens without these
    # fields. They retain their original static contact interpretation.
    contact_axis = None
    contact_origin = None
    use_kernel = False
    capture_points = None
    capture_key = None
    check_arm = False

    def __init__(self, points, geometry, pose_screen, *, opening: float = .08,
                 contact_points=None, contact_allowed: bool = False, payload_local=None,
                 initial_pose=None, measured_scene_points=None, measured_target_points=None,
                 use_kernel=False,capture_points=None,capture_key=None,check_arm=False):
        self.points = _point_array(points)
        self.use_kernel,self.capture_points,self.capture_key = use_kernel,capture_points,capture_key
        self.check_arm = check_arm
        self.tree = cKDTree(self.points) if len(self.points) else None
        self.geometry, self.ik, self.opening = geometry, pose_screen, opening
        self.target = _point_array(contact_points if contact_points is not None else [])
        # Prefix prediction must subtract instance pixels BEFORE choosing
        # scene/target voxel representatives. Independently sampled clouds
        # need not retain the same depth pixel from a shared voxel.
        self.measured_scene_points = (self.points if measured_scene_points is None
                                     else _point_array(measured_scene_points))
        self.measured_target_points = (self.target if measured_target_points is None
                                      else _point_array(measured_target_points))
        self.target_tree = cKDTree(self.target) if len(self.target) else None
        self.contact_allowed = contact_allowed
        self.payload = _point_array(payload_local if payload_local is not None else [])
        self._pose_geometry_cache = {}
        self._endpoint_ik_cache = {}
        self.radius = max(np.linalg.norm(np.maximum(np.abs(b["lower"]), np.abs(b["upper"])))
                          for b in geometry["boxes"])+.08
        if len(self.payload):
            self.radius = max(self.radius, float(np.linalg.norm(self.payload, axis=1).max()))
        self.initial_margin = {}
        self.initial_target_margin = {}
        self.initial_payload_margin = {}
        if initial_pose is not None and self.tree is not None:
            xyz = np.asarray(initial_pose['xyz_m'])
            rotation = Rotation.from_quat(initial_pose['quat_xyzw']).as_matrix()
            site = rotation@Rotation.from_euler('z', -math.pi/2).as_matrix()
            for points, tree, margin in ((self.points, self.tree, self.initial_margin),
                    (self.target, self.target_tree, self.initial_target_margin)):
                if tree is None:
                    continue
                ids = np.asarray(tree.query_ball_point(xyz, self.radius+.02), dtype=int)
                local = (points[ids]-xyz)@site
                for box in geometry['boxes']:
                    distance = self._halfspace_distance(local, box)
                    # The measured current pose is already occupied. Only a
                    # new/deeper incursion may reject its outgoing route.
                    keep = distance <= .004
                    if keep.any():
                        margin[box['name']] = dict(zip(ids[keep], distance[keep]))
            if len(self.payload):
                self._initial_payload_world = self.payload@rotation.T+xyz
                distances = cKDTree(self._initial_payload_world).sparse_distance_matrix(
                    self.tree, .004, output_type='coo_matrix')
                self.initial_payload_margin = {
                    (int(i), int(j)): float(d)
                    for i, j, d in zip(distances.row, distances.col, distances.data)}

    def rebase_start(self, robot):
        """Create this skill's start-clearance baseline from measured pose."""
        return self.with_measured_robot(robot)

    def with_measured_robot(self, robot):
        """Rebase outgoing clearance at the measured skill/braking start.

        The capture, contact permissions and geometry stay the same. Initial
        allowances are measured again, rather than inherited from a pose the
        preceding executed skill has already left.
        """
        current = PublicRouteScreen(self.points, self.geometry,
            self.ik.with_measured_robot(robot), opening=self.opening,
            contact_points=self.target, contact_allowed=self.contact_allowed,
            payload_local=self.payload,
            initial_pose={'xyz_m': robot['eef_xyz_m'], 'quat_xyzw': robot.get('eef_quat_xyzw', [0., 0., 0., 1.])},
            measured_scene_points=self.measured_scene_points,
            measured_target_points=self.measured_target_points,
            use_kernel=self.use_kernel, capture_points=self.capture_points,
            capture_key=self.capture_key, check_arm=self.check_arm)
        current.contact_axis, current.contact_origin = self.contact_axis, self.contact_origin
        current.support_separation = getattr(self, 'support_separation', False)
        return current

    def continuing_route(self):
        """Continue IK from a screened endpoint without changing calibration.

        The preceding full route has already reached ``last_solution``.
        Resetting its next local solve to the capture's original joints
        would test a joint-branch jump instead of the contact ingress.
        Captured obstacle geometry and initial clearance allowances stay
        unchanged; these planned joints are never reported as measurements.
        """
        if self.ik.last_solution is None:
            raise ValueError('a screened preceding route is required')
        current = copy.copy(self)
        current.ik = copy.copy(self.ik)
        current.ik.joints = self.ik.last_solution.copy()
        current.__dict__.pop('_geometry_kernel',None)
        return current

    def translating_contact(self, axis, measured_xyz):
        """Predict only the selected contact surface's axial displacement.

        Guarded translation measures actual progress after each increment;
        this conditional screen never establishes a successful articulation.
        Other measured scene points stay stationary obstacles.
        """
        current = copy.copy(self)
        current.contact_axis = axis
        current.contact_origin = np.asarray(measured_xyz, float).copy()
        current._pose_geometry_cache = {}
        current._endpoint_ik_cache = {}
        current.__dict__.pop('_geometry_kernel',None)
        return current

    def __getstate__(self):
        return {key:value for key,value in vars(self).items() if key not in {'_geometry_kernel'}}

    def endpoint_screen(self, route, robot):
        """Screen an endpoint without certifying its connecting trajectory.

        A fresh IK solver starts from the measured joints for every endpoint.
        Neither a preceding candidate's warm start nor a full route is used.
        The exact observed hand/payload geometry is checked only at the end;
        a clear endpoint leaves the connecting path's collision value unknown.
        """
        result = dict(collision=None, ik_reachable=None, path_min_clearance_m=None,
            screen_scope='endpoint_ik_coarse_geometry', passed=False)
        if not route or self.tree is None or self.ik is None:
            return {**result, 'reason':'public_screen_inputs_missing'}
        pose = route[-1]
        key = (tuple(pose['xyz_m']),tuple(pose['quat_xyzw']),json.dumps(robot,sort_keys=True))
        if key not in self._endpoint_ik_cache:
            solver = self.ik.with_measured_robot(robot)
            solver.warm_start = False
            self._endpoint_ik_cache[key] = solver.check(pose['xyz_m'], pose['quat_xyzw'])
        ik = self._endpoint_ik_cache[key]
        result['ik_reachable'] = bool(ik['solution_found'])
        result['endpoint_ik'] = ik
        if not result['ik_reachable']:
            return {**result, 'reason':'endpoint_numerical_ik_not_found'}
        geometry = self._geometry_at(pose)
        if not geometry['passed']:
            return {**result, 'collision':True, 'reason':geometry['reason']}
        return {**result, 'passed':True, 'reason':'endpoint_only_screen_passed'}

    def _halfspace_distance(self, local, box):
        shift = np.asarray(box.get('slide_per_half_opening', [0., 0., 0.]))*self.opening/2
        local = local-shift
        equations = box.get('convex_halfspaces')
        if equations is None:
            return np.maximum(np.asarray(box['lower'])-local, local-np.asarray(box['upper'])).max(axis=1)
        equations = np.asarray(equations)
        result = np.empty(len(local))
        for ids in np.array_split(np.arange(len(local)), max(1, (len(local)+255)//256)):
            result[ids] = (local[ids]@equations[:, :3].T+equations[:, 3]).max(axis=1)
        return result

    def _collisions(self, points, ids, xyz, site, initial_margin, *, pad_contact=False):
        if not initial_margin and not pad_contact:
            return (*collision_counts(points[ids], xyz, site, self.geometry, self.opening,
                clearance_m=.004, return_points=True), 0)
        local = (points[ids]-xyz)@site
        counts, hits, retained_margin = {}, {}, 0
        for box in self.geometry['boxes']:
            if pad_contact and box['name'].endswith('_pad'):
                continue
            shift = np.asarray(box.get('slide_per_half_opening', [0., 0., 0.]))*self.opening/2
            lower = np.asarray(box['lower'])+shift-.004
            upper = np.asarray(box['upper'])+shift+.004
            near = np.flatnonzero(
                (local[:, 0] >= lower[0]) & (local[:, 0] <= upper[0])
                & (local[:, 1] >= lower[1]) & (local[:, 1] <= upper[1])
                & (local[:, 2] >= lower[2]) & (local[:, 2] <= upper[2]))
            distance = self._halfspace_distance(local[near], box)
            baseline = initial_margin.get(box['name'], {})
            # A box can slide across the same measured surface. Pixel-pair
            # identity changes during translation/rotation and cannot define
            # penetration. Preserve the box's minimum occupied clearance.
            bound = min(baseline.values()) if baseline else .004
            blocked = (distance <= .004) & (distance < bound-1e-9)
            if not baseline:
                blocked |= distance <= .004
            retained_margin += int(((distance <= .004) & ~blocked).sum())
            if pad_contact:
                pad = next((candidate for candidate in self.geometry['boxes']
                    if candidate['name'] == box['name']+'_pad'), None)
                if pad is not None:
                    # Pad and finger meshes can overlap in the robot XML.
                    # Permit only that pad's contact region, not the whole
                    # finger shell sweeping through the selected object.
                    blocked &= self._halfspace_distance(local[near], pad) > .004
            counts[box['name']] = int(blocked.sum())
            hits[box['name']] = points[ids[near[blocked]]][:32].tolist()
        return counts, hits, retained_margin

    def __call__(self, poses: list[dict]) -> dict:
        base = {"source": "fused_rgbd_public_robot_and_static_geometry", "passed": False,
                "collision": None, "ik_reachable": None, "path_min_clearance_m": None,
                "screen_scope": "observed_hand_mesh_and_measured_payload;unseen_space_and_full_arm_not_certified",
                "samples": 0, "geometry_evaluations": 0, "clearance_certified_samples": 0, "ik_checks": []}
        if self.tree is None or self.ik is None:
            return {**base, "reason": "public_screen_inputs_missing"}
        if hasattr(self.ik, 'begin_route'):
            self.ik.begin_route()
        def dense_poses():
            # Reject the first blocked prefix before expanding a potentially
            # very long inherited-derivative braking route. The samples and
            # collision/IK tolerances are unchanged.
            yield poses[0], len(poses) == 1
            for index, (a, b) in enumerate(zip(poses[:-1], poses[1:])):
                p, q = np.asarray(a["xyz_m"]), np.asarray(b["xyz_m"])
                rotations = Rotation.from_quat([a["quat_xyzw"], b["quat_xyzw"]])
                angle = (rotations[1]*rotations[0].inv()).magnitude()
                n = max(1, math.ceil((np.linalg.norm(q-p)+self.radius*angle)/.004))
                slerp = Slerp([0., 1.], rotations)
                for part, t in enumerate(np.linspace(0., 1., n+1)[1:], 1):
                    yield {"xyz_m": ((1-t)*p+t*q).tolist(), "quat_xyzw": slerp(t).as_quat().tolist()}, (
                        index == len(poses)-2 and part == n)
        clearance = .2
        previous_support_clearances = {}
        last_ik = None
        certificate = None
        def prepared_poses():
            pending = iter(dense_poses())
            if not self.use_kernel or self.contact_axis is not None:
                yield from pending
                return
            # Reject an occupied measured start before expanding any future
            # spline or building a speculative batch of route poses.
            first = next(pending,None)
            if first is None:
                return
            yield first
            while True:
                batch = list(itertools.islice(pending,32))
                if not batch:
                    return
                if self.use_kernel and self.contact_axis is None:
                    from robots.libero.bounded_kernel_integration import geometry_kernel,can_accelerate
                    if can_accelerate(self):
                        geometry_kernel(self).prepare([pose for pose,_ in batch])
                yield from batch
        for pose, final in prepared_poses():
            xyz = np.asarray(pose["xyz_m"])
            rotation = Rotation.from_quat(pose["quat_xyzw"])
            motion_bound = (float(np.linalg.norm(xyz-certificate[0]))
                + self.radius*float((rotation*certificate[1].inv()).magnitude())) if certificate else float('inf')
            if self.contact_axis is None and certificate and certificate[2]-motion_bound > math.sqrt(3)*.004:
                # Distance to any observed point is 1-Lipschitz in the
                # maximum displacement of the hand/payload surface. This
                # certificate includes allowed-contact exclusions and target
                # geometry; it never relies on endpoint checks alone. The
                # collision broad phase expands every box axis by 4 mm, so
                # its corners require sqrt(3)*4 mm in Euclidean distance.
                geometry = {'passed': True, 'path_min_clearance_m': certificate[2]-motion_bound}
                base['clearance_certified_samples'] += 1
            else:
                geometry = self._geometry_at(pose)
                base['geometry_evaluations'] += 1
                if geometry['passed']:
                    certificate = xyz, rotation, geometry['path_min_clearance_m']
            support_clearances = geometry.get('occupied_support_clearances_m', {})
            if any(group in previous_support_clearances
                    and value < previous_support_clearances[group]-1e-9
                    for group, value in support_clearances.items()):
                geometry = {**geometry, 'passed':False,'collision':True,
                    'reason':'measured_support_separation_decreased'}
            previous_support_clearances.update(support_clearances)
            base["samples"] += 1
            clearance = min(clearance, geometry["path_min_clearance_m"])
            if not geometry["passed"]:
                return {**base, **geometry, "at": pose}
            signature = np.r_[xyz, rotation.as_rotvec()*.15]
            if last_ik is None or np.linalg.norm(signature-last_ik) >= .02 or final:
                result = self.ik.check(xyz, pose["quat_xyzw"])
                base["ik_checks"].append({"xyz_m": xyz.tolist(), **result})
                if not result["solution_found"]:
                    return {**base, "reason": "numerical_ik_not_found", "collision": False,
                            "ik_reachable": False, "path_min_clearance_m": max(0., clearance),
                            "at": pose}
                last_ik = signature
        if self.check_arm:
            from robots.libero.bounded_arm_screen import screen_arm_route
            arm = screen_arm_route(self,base['ik_checks'])
            base['arm_screen'] = arm
            if not arm['passed']:
                return {**base,'reason':arm['reason'],'collision':True,'ik_reachable':True,
                    'path_min_clearance_m':0.,'at':{'joint_positions_rad':arm['joint_positions_rad']}}
        return {**base, "passed": True, "reason": "public_route_screen_passed", "collision": False,
                "ik_reachable": True, "path_min_clearance_m": max(0., clearance)}


    def _payload_groups(self):
        """Connected obstacle surfaces from this immutable measured capture."""
        if not hasattr(self, '_payload_obstacle_groups'):
            from scipy.sparse import coo_matrix
            from scipy.sparse.csgraph import connected_components
            cells, inverse = np.unique(np.floor(self.points/.008).astype(np.int64),
                axis=0, return_inverse=True)
            pairs = cKDTree(cells).query_pairs(1.75, output_type='ndarray')
            n = len(cells)
            graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
            _, groups = connected_components(graph, directed=False)
            self._payload_obstacle_groups = groups[inverse]
        return self._payload_obstacle_groups

    def _support_planes(self):
        """Fit occupied support patches, not nearest depth-pixel distances.

        A lateral subpixel move can reduce unsigned point-to-point distance
        while the payload separates from the actual measured surface. Only
        locally planar occupied patches get this signed-distance treatment;
        other obstacles retain the exact point-cloud collision check.
        """
        if not hasattr(self, '_occupied_support_planes'):
            groups = self._payload_groups()
            occupied = {}
            for _, j in self.initial_payload_margin:
                occupied.setdefault(int(groups[j]), set()).add(j)
            planes = {}
            for group, ids in occupied.items():
                contacts = self.points[sorted(ids)]
                neighbours = np.unique(np.concatenate(self.tree.query_ball_point(contacts, .02)))
                patch = self.points[neighbours[groups[neighbours] == group]]
                if len(patch) < 6:
                    continue
                centre = patch.mean(0)
                _, singular, axes = np.linalg.svd(patch-centre, full_matrices=False)
                # A line or a curved/corner patch cannot establish a support
                # plane. The residual bound describes observed flatness,
                # never an extra collision clearance.
                if singular[1] < .002 or singular[2] > .05*singular[1]:
                    continue
                normal = axes[-1]
                residual = np.abs((patch-centre)@normal)
                if residual.max() > .001:
                    continue
                origin = getattr(self, '_initial_payload_world', None)
                if origin is None:
                    continue
                if (origin.mean(0)-centre)@normal < 0:
                    normal = -normal
                planes[group] = {'centre': centre, 'normal': normal,
                    'flatness_m': float(residual.max()),
                    'initial_clearance_m': float(((origin-centre)@normal).min())}
            self._occupied_support_planes = planes
        return self._occupied_support_planes

    def _geometry_at(self,pose):
        key = (*pose['xyz_m'],*pose['quat_xyzw'])
        if key in self._pose_geometry_cache:
            return self._pose_geometry_cache[key]
        if self.use_kernel and self.contact_axis is None:
            from robots.libero.bounded_kernel_integration import geometry_kernel,can_accelerate
            # Reject the current pose before constructing any unused field.
            # Warm hand-only screens were faster without a new EDT in C2's
            # real corpus; they can reuse a payload-built capture field.
            if self._pose_geometry_cache and can_accelerate(self):
                result = geometry_kernel(self).geometry_at(pose)
                if result.get('initial_margin_policy')=='positive_clearance_no_further_incursion':
                    result = {**result,'initial_margin_policy':'measured_current_overlap_no_further_incursion'}
                self._pose_geometry_cache[key] = result
                return result
        return self._geometry_exact(pose)

    def _geometry_exact(self, pose):
        """Reuse exact-pose tests only within this immutable measured screen.

        Every sampled pose is still checked. Shared trajectory prefixes and
        repeated align endpoints need not repeat the same mesh calculations.
        A refresh constructs a new screen, so changed pixels/opening/payload
        cannot reuse a prior capture's result.
        """
        key = (*pose["xyz_m"], *pose["quat_xyzw"])
        if key in self._pose_geometry_cache:
            return self._pose_geometry_cache[key]
        xyz = np.asarray(pose["xyz_m"])
        rotation = Rotation.from_quat(pose["quat_xyzw"])
        site = rotation.as_matrix()@Rotation.from_euler("z", -math.pi/2).as_matrix()
        nearby_ids = np.asarray(self.tree.query_ball_point(xyz, self.radius+.02), dtype=int)
        nearby = self.points[nearby_ids]
        counts, scene_hits, retained_margin = self._collisions(
            self.points, nearby_ids, xyz, site, self.initial_margin)
        shift = np.zeros(3)
        if self.contact_axis is not None:
            shift[self.contact_axis] = xyz[self.contact_axis]-self.contact_origin[self.contact_axis]
        target = self.target+shift if self.contact_axis is not None else self.target
        target_ids = np.asarray(self.target_tree.query_ball_point(xyz-shift, self.radius+.02), dtype=int) if self.target_tree is not None else np.empty(0, dtype=int)
        own_points = target[target_ids]
        own, target_hits, retained_target_margin = self._collisions(
            target, target_ids, xyz, site, self.initial_target_margin,
            pad_contact=self.contact_allowed)
        if any(counts.values()) or any(own.values()):
            result = {"passed": False, "reason": "measured_sweep_collision", "collision": True,
                "counts": counts, "target_counts": own, "path_min_clearance_m": 0.,
                "public_scene_collision_points": scene_hits, "public_target_collision_points": target_hits,
                "public_nearby_points": nearby[:256].tolist()}
        else:
            clearance = .2
            target_boxes = [b for b in self.geometry['boxes']
                if not self.contact_allowed or not b['name'].endswith('_pad')]
            for cloud, boxes in ((nearby, self.geometry['boxes']), (own_points, target_boxes)):
                local = (cloud-xyz)@site
                for box in boxes:
                    shift = np.asarray(box.get("slide_per_half_opening", [0, 0, 0]))*self.opening/2
                    if len(local):
                        separation = np.maximum(np.maximum(np.asarray(box["lower"])+shift-local,
                            local-(np.asarray(box["upper"])+shift)), 0.)
                        clearance = min(clearance, float(np.linalg.norm(separation, axis=1).min()))
            # Points outside the radius query can still approach a future
            # pose. Cap the certificate by the guaranteed unseen-query gap.
            clearance = min(clearance, .02)
            result = {"passed": True, "path_min_clearance_m": clearance}
            if len(self.payload):
                world_payload = self.payload@rotation.as_matrix().T+xyz
                distances, neighbours = self.tree.query(world_payload)
                at = int(np.argmin(distances))
                payload_clearance = float(distances[at])
                result["path_min_clearance_m"] = min(clearance, payload_clearance)
                if payload_clearance < .004:
                    blocked = True
                    if self.initial_payload_margin:
                        # Group connected measured obstacle surfaces. An
                        # attached body's nearest sampled point may change
                        # while separating from its support; the surface's
                        # minimum clearance must not decrease.
                        groups = (self._payload_groups() if getattr(self, 'support_separation', False)
                            else np.arange(len(self.points)))
                        previous = np.full(int(groups.max())+1, np.inf)
                        for (_, j), distance in self.initial_payload_margin.items():
                            previous[groups[j]] = min(previous[groups[j]], distance)
                        pairs = cKDTree(world_payload).sparse_distance_matrix(
                            self.tree, .004, output_type='coo_matrix')
                        if getattr(self, 'support_separation', False):
                            bounds = previous[groups[pairs.col]]
                            violations = (pairs.data < bounds-1e-9) | ~np.isfinite(bounds)
                            occupied = np.isfinite(bounds)
                            clearances = {int(group): float(pairs.data[(groups[pairs.col] == group) & occupied].min())
                                for group in np.unique(groups[pairs.col[occupied]])}
                            planes = self._support_planes()
                            for group, plane in planes.items():
                                plane_pairs = ((groups[pairs.col] == group)
                                    & (np.abs((self.points[pairs.col]-plane['centre'])@plane['normal'])
                                        <= plane['flatness_m']+1e-6))
                                signed = float(((world_payload-plane['centre'])@plane['normal']).min())
                                violations[plane_pairs] = signed < plane['initial_clearance_m']-1e-9
                                clearances[group] = signed
                            result['occupied_support_clearances_m'] = clearances
                            result['support_plane_count'] = len(planes)
                            result['occupied_support_clearance_m'] = (float(pairs.data[occupied].min())
                                if occupied.any() else .004)
                        else:
                            bounds = np.array([self.initial_payload_margin.get((int(i), int(j)), .004)
                                for i, j in zip(pairs.row, pairs.col)])
                            violations = (pairs.data < bounds-1e-9) | np.array([
                                (int(i), int(j)) not in self.initial_payload_margin
                                for i, j in zip(pairs.row, pairs.col)], dtype=bool)
                        blocked = bool(violations.any())
                        result['initial_payload_margin_pairs_retained'] = int((~violations).sum())
                        result['initial_margin_policy'] = 'measured_surface_minimum_no_further_incursion'
                        if blocked:
                            hit = np.flatnonzero(violations)[np.argmin(pairs.data[violations])]
                            at, neighbour = pairs.row[hit], pairs.col[hit]
                        else:
                            neighbour = neighbours[at]
                    else:
                        neighbour = neighbours[at]
                    if blocked:
                        result.update(passed=False, reason="measured_payload_collision", collision=True,
                            payload_point=world_payload[at].tolist(),
                            obstacle_point=self.points[neighbour].tolist())
        if self.initial_margin:
            result['initial_margin_policy'] = 'measured_current_overlap_no_further_incursion'
            result['initial_margin_pairs_retained'] = retained_margin
        if self.initial_target_margin:
            result['initial_margin_policy'] = 'measured_current_overlap_no_further_incursion'
            result['initial_target_margin_pairs_retained'] = retained_target_margin
        self._pose_geometry_cache[key] = result
        return result
