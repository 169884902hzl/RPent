# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Propose public-kinematic guides; only the full route screen may accept one."""

from __future__ import annotations

import copy

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_grasp_kinematics import forward_jacobian


def contact_guides(screen, robot, candidates):
    """Yield measured contact poses reached along joint-interpolated guides.

    Numerical endpoint IK is only a proposal generator. Every returned guide
    still needs the unchanged Cartesian sweep, continuation IK and execution
    checks. No object pose, task predicate or joint actuator command is used.
    """
    start = np.asarray(robot['joint_positions_rad'])
    proposals, seen = [], set()
    for candidate in candidates:
        if candidate.get('closure'):
            continue
        key = (*candidate['xyz_m'], *candidate['quat_xyzw'])
        if key in seen:
            continue
        seen.add(key)
        ik = copy.deepcopy(screen.ik)
        ik.route_joint_step_rad, ik.last_solution, ik.cache = None, None, {}
        endpoint = ik.check(candidate['xyz_m'], candidate['quat_xyzw'])
        solution = next((solve for solve in endpoint['solves'] if solve['solution_found']), None)
        if solution is not None:
            goal = np.asarray(solution['joint_positions_rad'])
            proposals.append((float(np.linalg.norm(goal-start)), candidate, goal))
    for distance, candidate, goal in sorted(proposals, key=lambda item: item[0]):
        route = []
        samples = max(2, int(np.ceil(np.max(np.abs(goal-start))/.04)))
        for fraction in np.linspace(0, 1, samples+1)[1:]:
            joints = start+(goal-start)*fraction
            pose, site, _ = forward_jacobian(screen.ik.nodes, joints, screen.ik.site_offset)
            route.append({'xyz_m': (screen.ik.world_offset+screen.ik.world_rotation@site).tolist(),
                'quat_xyzw': Rotation.from_matrix(screen.ik.world_rotation@pose[:3, :3]).as_quat().tolist()})
        route.append({'xyz_m': candidate['xyz_m'], 'quat_xyzw': candidate['quat_xyzw']})
        # Retain the last >=4 cm separation as the precontact boundary.
        # The remainder follows this same guide, rather than an independently
        # invented straight descent to an unreachable normal stand-off.
        contact = np.asarray(candidate['xyz_m'])
        boundary = next((index for index in reversed(range(len(route)-1))
                         if np.linalg.norm(np.asarray(route[index]['xyz_m'])-contact) >= .04), None)
        if boundary is None:
            continue
        yield {**candidate, 'route': route, 'screen': None,
            'approach_xyz_m': route[boundary]['xyz_m'], 'approach_route': route[:boundary+1],
            'contact_route': route[boundary+1:], 'path': 'around',
            'route_proposal': 'public_joint_interpolation_cartesian_waypoints/1',
            'joint_distance_rad': distance}
