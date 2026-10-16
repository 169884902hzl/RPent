"""Mesh sweep and numerical IK for a sampled public RGB-D trajectory."""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp

from robots.libero.v5_geometric_grasp import collision_counts


class PublicRouteScreen:
    """Reuses r9 hulls and IK; certifies only observed hand/payload geometry."""

    def __init__(self, points, geometry, pose_screen, *, opening: float = .08,
                 contact_points=None, contact_allowed: bool = False, payload_local=None):
        self.points = np.asarray(points, float).reshape(-1, 3)
        self.tree = cKDTree(self.points) if len(self.points) else None
        self.geometry, self.ik, self.opening = geometry, pose_screen, opening
        self.target = np.asarray(contact_points if contact_points is not None else [], float).reshape(-1, 3)
        self.target_tree = cKDTree(self.target) if len(self.target) else None
        self.contact_allowed = contact_allowed
        self.payload = np.asarray(payload_local if payload_local is not None else [], float).reshape(-1, 3)
        self.radius = max(np.linalg.norm(np.maximum(np.abs(b["lower"]), np.abs(b["upper"])))
                          for b in geometry["boxes"])+.08

    def __call__(self, poses: list[dict]) -> dict:
        base = {"source": "fused_rgbd_public_robot_and_static_geometry", "passed": False,
                "collision": None, "ik_reachable": None, "path_min_clearance_m": None,
                "screen_scope": "observed_hand_mesh_and_measured_payload;unseen_space_and_full_arm_not_certified",
                "samples": 0, "ik_checks": []}
        if self.tree is None or self.ik is None:
            return {**base, "reason": "public_screen_inputs_missing"}
        dense = [poses[0]]
        for a, b in zip(poses[:-1], poses[1:]):
            p, q = np.asarray(a["xyz_m"]), np.asarray(b["xyz_m"])
            rotations = Rotation.from_quat([a["quat_xyzw"], b["quat_xyzw"]])
            angle = (rotations[1]*rotations[0].inv()).magnitude()
            n = max(1, math.ceil((np.linalg.norm(q-p)+self.radius*angle)/.004))
            slerp = Slerp([0., 1.], rotations)
            dense.extend({"xyz_m": ((1-t)*p+t*q).tolist(), "quat_xyzw": slerp(t).as_quat().tolist()}
                         for t in np.linspace(0., 1., n+1)[1:])
        clearance = .2
        last_ik = None
        for pose in dense:
            xyz = np.asarray(pose["xyz_m"])
            rotation = Rotation.from_quat(pose["quat_xyzw"])
            site = rotation.as_matrix()@Rotation.from_euler("z", -math.pi/2).as_matrix()
            nearby = self.points[self.tree.query_ball_point(xyz, self.radius+.02)]
            counts = collision_counts(nearby, xyz, site, self.geometry, self.opening, clearance_m=.004)
            # The hand is contained in radius for every orientation. Distant
            # target pixels cannot collide with it; use the same broad phase
            # as the scene instead of transforming the full mask each tick.
            own_points = self.target[self.target_tree.query_ball_point(xyz, self.radius+.02)] if self.target_tree is not None else self.target
            own = collision_counts(own_points, xyz, site, self.geometry, self.opening, clearance_m=.004)
            if self.contact_allowed:
                own = {k: v for k, v in own.items() if k == "palm"}
            base["samples"] += 1
            if any(counts.values()) or any(own.values()):
                return {**base, "reason": "measured_sweep_collision", "collision": True,
                        "at": pose, "counts": counts, "target_counts": own, "path_min_clearance_m": 0.,
                        "public_nearby_points": nearby[:256].tolist()}
            # Distance to enclosing AABBs is a conservative lower bound on
            # mesh clearance. Exact convex hull tests above still decide
            # collisions; do not repeat all hull halfspaces just for ranking.
            local = (nearby-xyz)@site
            for box in self.geometry["boxes"]:
                shift = np.asarray(box.get("slide_per_half_opening", [0, 0, 0]))*self.opening/2
                if len(local):
                    separation = np.maximum(np.maximum(np.asarray(box["lower"])+shift-local,
                        local-(np.asarray(box["upper"])+shift)), 0.)
                    clearance = min(clearance, float(np.linalg.norm(separation, axis=1).min()))
            if len(self.payload):
                world_payload = self.payload@rotation.as_matrix().T+xyz
                distances, neighbours = self.tree.query(world_payload)
                at = int(np.argmin(distances))
                payload_clearance = float(distances[at])
                clearance = min(clearance, payload_clearance)
                if payload_clearance < .004:
                    return {**base, "reason": "measured_payload_collision", "collision": True,
                            "at": pose, "path_min_clearance_m": payload_clearance,
                            "payload_point": world_payload[at].tolist(),
                            "obstacle_point": self.points[neighbours[at]].tolist()}
            signature = np.r_[xyz, rotation.as_rotvec()*.15]
            if last_ik is None or np.linalg.norm(signature-last_ik) >= .02 or pose is dense[-1]:
                result = self.ik.check(xyz, pose["quat_xyzw"])
                base["ik_checks"].append({"xyz_m": xyz.tolist(), **result})
                if not result["solution_found"]:
                    return {**base, "reason": "numerical_ik_not_found", "collision": False,
                            "ik_reachable": False, "path_min_clearance_m": max(0., clearance)}
                last_ik = signature
        return {**base, "passed": True, "reason": "public_route_screen_passed", "collision": False,
                "ik_reachable": True, "path_min_clearance_m": max(0., clearance)}
