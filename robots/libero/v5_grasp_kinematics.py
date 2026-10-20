# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Panda pose screening from static robot geometry and public proprioception.

Numerical IK screens a candidate; it cannot certify arm collision avoidance
or convergence of the Cartesian servo. No simulator scene state is read.
"""
from functools import lru_cache
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

VERSION = "public-panda-pose-screen/1-dev"


@lru_cache(maxsize=2)
def robot_chain(xml_path):
    path = Path(xml_path)
    root = ET.fromstring(path.read_bytes())

    def find(body, parents):
        chain = parents + [body]
        if body.get("name") == "right_hand":
            return chain
        for child in body.findall("body"):
            result = find(child, chain)
            if result is not None:
                return result
        return None

    chain = find(root.find("worldbody/body"), [])
    nodes, limits = [], []
    for body in chain:
        w, x, y, z = np.fromstring(body.get("quat", "1 0 0 0"), sep=" ")
        transform = np.eye(4)
        transform[:3, :3] = Rotation.from_quat([x, y, z, w]).as_matrix()
        transform[:3, 3] = np.fromstring(body.get("pos", "0 0 0"), sep=" ")
        joint = body.find("joint")
        axis = None
        if joint is not None:
            if joint.get("type", "hinge") != "hinge" or not np.allclose(
                    np.fromstring(joint.get("pos", "0 0 0"), sep=" "), 0.):
                raise ValueError("seven zero-offset Panda hinge joints required")
            axis = np.fromstring(joint.get("axis", "0 0 1"), sep=" ")
            limits.append(np.fromstring(joint.get("range"), sep=" "))
        nodes.append((transform, axis))
    if len(limits) != 7:
        raise ValueError("seven Panda joint limits required")
    return nodes, np.asarray(limits), {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def forward(nodes, joints):
    result, index = np.eye(4), 0
    for transform, axis in nodes:
        result = result @ transform
        if axis is not None:
            rotation = np.eye(4)
            rotation[:3, :3] = Rotation.from_rotvec(axis * joints[index]).as_matrix()
            result = result @ rotation
            index += 1
    return result


def forward_jacobian(nodes, joints, site_offset):
    """Static FK and geometric site Jacobian in the robot description frame."""
    pose, index, axes, origins = np.eye(4), 0, [], []
    for fixed, axis in nodes:
        pose = pose@fixed
        if axis is not None:
            axes.append(pose[:3, :3]@axis)
            origins.append(pose[:3, 3].copy())
            turn = np.eye(4)
            turn[:3, :3] = Rotation.from_rotvec(axis*joints[index]).as_matrix()
            pose = pose@turn
            index += 1
    site = pose[:3, 3]+pose[:3, :3]@site_offset
    jacobian = np.r_[np.cross(np.asarray(axes), site-np.asarray(origins)).T, np.asarray(axes).T]
    return pose, site, jacobian


def rotation_error_jacobian(error):
    """Right SO(3) log Jacobian inverse for world angular perturbations."""
    x, y, z = error
    skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    angle = np.linalg.norm(error)
    scale = 1/12 if angle < 1e-5 else (1-.5*angle/np.tan(.5*angle))/angle**2
    return np.eye(3)+.5*skew+scale*(skew@skew)


@lru_cache(maxsize=2)
def robot_link_hulls(xml_path):
    """Static collision meshes in each public kinematic chain node frame."""
    from scipy.spatial import ConvexHull
    from robots.libero.v5_geometric_grasp import stl_vertices, _rotation, _vector

    path = Path(xml_path)
    root = ET.fromstring(path.read_bytes())
    meshes = {mesh.get('name'): path.parent/mesh.get('file')
              for mesh in root.findall('asset/mesh')}
    bodies, result = [], []
    body = root.find('worldbody/body')
    while body is not None:
        bodies.append(body)
        if body.get('name') == 'right_hand':
            break
        body = body.find('body')
    for index, body in enumerate(bodies):
        for geom in body.findall('geom'):
            if geom.get('group') != '0' or geom.get('type') != 'mesh':
                continue
            mesh = meshes[geom.get('mesh')]
            vertices = stl_vertices(mesh)@_rotation(geom).T+_vector(geom,'pos','0 0 0')
            result.append({'node': index, 'name': body.get('name'),
                           'lower': vertices.min(axis=0), 'upper': vertices.max(axis=0),
                           'equations': ConvexHull(vertices).equations,
                           'mesh': {'path': str(mesh), 'sha256': hashlib.sha256(mesh.read_bytes()).hexdigest()}})
    return result


class PublicPoseScreen:
    use_batched_kernel = False
    def __init__(self, robot_xml, joints, eef_xyz, hand_quat_xyzw, site_offset_hand, *, warm_start=False):
        self.nodes, self.limits, self.reference = robot_chain(str(robot_xml))
        self.joints = np.asarray(joints, dtype=float)
        if self.joints.shape != (7,) or not np.isfinite(self.joints).all():
            raise ValueError("seven measured public robot joint positions required")
        self.site_offset = np.asarray(site_offset_hand, dtype=float)
        current = forward(self.nodes, self.joints)
        self.world_rotation = Rotation.from_quat(hand_quat_xyzw).as_matrix() @ current[:3, :3].T
        site = current[:3, 3] + current[:3, :3] @ self.site_offset
        self.world_offset = np.asarray(eef_xyz) - self.world_rotation @ site
        self.cache = {}
        self.warm_start, self.last_solution = warm_start, None
        self.route_joint_step_rad = None

    def with_measured_robot(self, robot):
        """Seed a new route from its current public joint/EEF measurement."""
        result = type(self)(self.reference['path'], robot['joint_positions_rad'],
            robot['eef_xyz_m'], robot['eef_quat_xyzw'], self.site_offset,
            warm_start=self.warm_start)
        result.use_batched_kernel = self.use_batched_kernel
        return result

    def begin_route(self, *, max_joint_step_rad=.35):
        """Start a local IK continuation at this capture's measured joints.

        The local solve box rejects branch jumps between nearby Cartesian
        samples. It is a numerical search bound, not a robot speed command
        or proof that no continuous joint route exists outside that box.
        """
        self.route_joint_step_rad = float(max_joint_step_rad)
        if not np.isfinite(self.route_joint_step_rad) or self.route_joint_step_rad <= 0:
            raise ValueError('positive local IK continuation bound required')
        self.last_solution = np.clip(self.joints, self.limits[:, 0]+1e-6, self.limits[:, 1]-1e-6).copy()

    def remove_measured_arm(self, points, *, tolerance_m=.002):
        """Remove current robot surfaces using only joint sensors and static meshes.

        Moving the hand does not move the arm's old RGB-D pixels. Those pixels
        must not become static scene obstacles during the swept-route test.
        This filter is not a test of future arm-link collisions.
        """
        cloud = np.asarray(points, dtype=float)
        poses, pose, joint = [], np.eye(4), 0
        for transform, axis in self.nodes:
            pose = pose@transform
            if axis is not None:
                turn = np.eye(4)
                turn[:3,:3] = Rotation.from_rotvec(axis*self.joints[joint]).as_matrix()
                pose = pose@turn
                joint += 1
            poses.append(pose.copy())
        occupied = np.zeros(len(cloud), dtype=bool)
        counts = {}
        # Matches the route's base 2 mm mesh margin; no broad carve around
        # the target, table, fixtures, or robot workspace is performed.
        tolerance = tolerance_m
        base_points = (cloud-self.world_offset)@self.world_rotation
        for hull in robot_link_hulls(self.reference['path']):
            transform = poses[hull['node']]
            local = (base_points-transform[:3,3])@transform[:3,:3]
            broad = ((local>=hull['lower']-tolerance)&(local<=hull['upper']+tolerance)).all(axis=1)
            ids = np.flatnonzero(broad&~occupied)
            equations = hull['equations']
            removed = 0
            for batch in np.array_split(ids, max(1, (len(ids)+255)//256)):
                supported = ((local[batch]@equations[:,:3].T+equations[:,3])<=tolerance).all(axis=1)
                occupied[batch[supported]] = True
                removed += int(supported.sum())
            counts[hull['name']] = removed
        return cloud[~occupied], {'version':'public-current-robot-surface-filter/1-dev',
            'source':'static_robot_collision_meshes_and_public_joint_sensors',
            'removed_points': int(occupied.sum()), 'per_link': counts,
            'margin_m': tolerance, 'future_arm_collisions_checked': False,
            'robot_description':self.reference,
            'meshes':[hull['mesh'] for hull in robot_link_hulls(self.reference['path'])]}

    def check(self, xyz, hand_quat_xyzw):
        key = (*map(float, xyz), *map(float, hand_quat_xyzw))
        lower, upper = self.limits[:, 0]+1e-6, self.limits[:, 1]-1e-6
        reference = self.last_solution if self.last_solution is not None else self.joints
        if self.route_joint_step_rad is not None:
            lower = np.maximum(lower, reference-self.route_joint_step_rad)
            upper = np.minimum(upper, reference+self.route_joint_step_rad)
            # A pose can be reachable from one elbow branch and unreachable
            # from another. Its cache must include the incoming joint state.
            key = (*key, *reference)
        if key in self.cache:
            cached = self.cache[key]
            if cached['solution_found'] and (self.warm_start or self.route_joint_step_rad is not None):
                self.last_solution = np.asarray(next(s['joint_positions_rad'] for s in cached['solves'] if s['solution_found']))
            return cached
        if self.use_batched_kernel and not self.warm_start and self.route_joint_step_rad is None:
            from robots.libero.bounded_kernels.ik import BatchedDampedIK
            kernel = BatchedDampedIK.from_source(self)
            if self.route_joint_step_rad is not None:
                kernel.max_joint_step_rad = self.route_joint_step_rad
            trial = kernel.solve_batch([xyz],[hand_quat_xyzw],reference,
                continuity=self.route_joint_step_rad is not None)
            if trial['solution_found'][0]:
                joints = trial['joint_positions_rad'][0]
                pose,site,_ = forward_jacobian(self.nodes,joints,self.site_offset)
                p = float(np.linalg.norm(self.world_offset+self.world_rotation@site-xyz))
                angle = float((Rotation.from_quat(hand_quat_xyzw)*
                    Rotation.from_matrix(self.world_rotation@pose[:3,:3]).inv()).magnitude())
                if p<.008 and angle<.05 and (joints>=lower).all() and (joints<=upper).all():
                    if self.warm_start or self.route_joint_step_rad is not None:
                        self.last_solution = joints.copy()
                    evidence = {'version':VERSION,'source':'static_robot_description_and_public_proprioception',
                        'robot_xml':self.reference,'solution_found':True,'solves':[{
                            'position_error_m':p,'orientation_error_rad':angle,'joint_positions_rad':joints.tolist(),
                            'joint_margin_min_rad':float(np.minimum(joints-self.limits[:,0],self.limits[:,1]-joints).min()),
                            'function_evaluations':int(trial['function_evaluations'][0]),'solution_found':True,
                            'method':'c2_batched_damped_least_squares_independent_source_fk_verified'}],
                        'numerical_failure_is_not_proof_of_infeasibility':True,
                        'arm_collisions_checked':False,'servo_convergence_certified':False}
                    if self.route_joint_step_rad is not None:
                        evidence['local_continuation']={'max_joint_step_rad':self.route_joint_step_rad,
                            'from_joint_positions_rad':reference.tolist(),'numerical_search_bound_only':True}
                    self.cache[key] = evidence
                    return evidence
        position, desired = np.asarray(xyz), Rotation.from_quat(hand_quat_xyzw)

        last = None
        def evaluate(joints):
            nonlocal last
            if last is not None and np.array_equal(joints, last[0]):
                return last[1:]
            pose, site, jacobian = forward_jacobian(self.nodes, joints, self.site_offset)
            site = self.world_offset+self.world_rotation@site
            rotation = Rotation.from_matrix(self.world_rotation @ pose[:3, :3])
            error = (desired*rotation.inv()).as_rotvec()
            value = np.r_[site-position, .15*error]
            derivative = np.r_[self.world_rotation@jacobian[:3],
                -.15*rotation_error_jacobian(error)@self.world_rotation@jacobian[3:]]
            last = (joints.copy(), value, derivative)
            return value, derivative

        def residual(joints):
            return evaluate(joints)[0]

        solves = []
        if self.warm_start:
            # Dense route samples are close to the preceding accepted pose.
            # Stop at the same screening tolerances instead of optimizing a
            # seven-joint redundant solution down to machine precision.
            joints = np.clip(self.last_solution if self.last_solution is not None else self.joints,
                             lower, upper).copy()
            for iteration in range(16):
                value, jacobian = evaluate(joints)
                p, angle = np.linalg.norm(value[:3]), np.linalg.norm(value[3:])/.15
                if p < .008 and angle < .05:
                    self.last_solution = joints.copy()
                    evidence = {"version": VERSION, "source": "static_robot_description_and_public_proprioception",
                        "robot_xml": self.reference, "solution_found": True,
                        "solves": [{"position_error_m": float(p), "orientation_error_rad": float(angle),
                            "joint_positions_rad": joints.tolist(), "function_evaluations": iteration+1,
                            "joint_margin_min_rad": float(np.min(np.minimum(joints-self.limits[:, 0], self.limits[:, 1]-joints))),
                            "solution_found": True, "method": "warm_damped_jacobian"}],
                        "numerical_failure_is_not_proof_of_infeasibility": True,
                        "arm_collisions_checked": False, "servo_convergence_certified": False}
                    if self.route_joint_step_rad is not None:
                        evidence['local_continuation'] = {'max_joint_step_rad': self.route_joint_step_rad,
                            'from_joint_positions_rad': reference.tolist(), 'numerical_search_bound_only': True}
                    self.cache[key] = evidence
                    return evidence
                delta = -jacobian.T@np.linalg.solve(jacobian@jacobian.T+np.eye(6)*1e-5, value)
                delta *= min(1., .2/max(np.linalg.norm(delta), 1e-12))
                updated = np.clip(joints+delta, lower, upper)
                if np.linalg.norm(updated-joints) < 1e-9:
                    break
                joints = updated
        seeds = (self.joints, np.array([0., -.4, 0., -2.2, 0., 2., .75]),
                 np.array([.8, -.4, -.8, -2.2, .8, 2., -.75]))
        if self.warm_start and self.last_solution is not None:
            seeds = (self.last_solution, *seeds)
        for seed in seeds:
            result = least_squares(residual, np.clip(seed, lower, upper),
                jac=lambda joints: evaluate(joints)[1],
                bounds=(lower, upper), max_nfev=120,
                ftol=1e-8, xtol=1e-8, gtol=1e-8)
            error = residual(result.x)
            p, angle = float(np.linalg.norm(error[:3])), float(np.linalg.norm(error[3:])/.15)
            solves.append({"position_error_m": p, "orientation_error_rad": angle,
                'joint_positions_rad': result.x.tolist(),
                "joint_margin_min_rad": float(np.min(np.minimum(
                    result.x-self.limits[:, 0], self.limits[:, 1]-result.x))),
                "function_evaluations": result.nfev, "solution_found": p < .008 and angle < .05})
            if solves[-1]["solution_found"]:
                if self.warm_start or self.route_joint_step_rad is not None:
                    self.last_solution = result.x.copy()
                break
        evidence = {"version": VERSION, "source": "static_robot_description_and_public_proprioception",
            "robot_xml": self.reference, "solution_found": any(s["solution_found"] for s in solves),
            "solves": solves, "numerical_failure_is_not_proof_of_infeasibility": True,
            "arm_collisions_checked": False, "servo_convergence_certified": False}
        if self.route_joint_step_rad is not None:
            evidence['local_continuation'] = {'max_joint_step_rad': self.route_joint_step_rad,
                'from_joint_positions_rad': reference.tolist(), 'numerical_search_bound_only': True}
        self.cache[key] = evidence
        return evidence
