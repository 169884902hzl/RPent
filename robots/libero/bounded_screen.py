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
        self._pose_geometry_cache = {}
        self.radius = max(np.linalg.norm(np.maximum(np.abs(b["lower"]), np.abs(b["upper"])))
                          for b in geometry["boxes"])+.08
        if len(self.payload):
            self.radius = max(self.radius, float(np.linalg.norm(self.payload, axis=1).max()))

    def __call__(self, poses: list[dict]) -> dict:
        base = {"source": "fused_rgbd_public_robot_and_static_geometry", "passed": False,
                "collision": None, "ik_reachable": None, "path_min_clearance_m": None,
                "screen_scope": "observed_hand_mesh_and_measured_payload;unseen_space_and_full_arm_not_certified",
                "samples": 0, "geometry_evaluations": 0, "clearance_certified_samples": 0, "ik_checks": []}
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
        certificate = None
        for pose in dense:
            xyz = np.asarray(pose["xyz_m"])
            rotation = Rotation.from_quat(pose["quat_xyzw"])
            motion_bound = (float(np.linalg.norm(xyz-certificate[0]))
                + self.radius*float((rotation*certificate[1].inv()).magnitude())) if certificate else float('inf')
            if certificate and certificate[2]-motion_bound > math.sqrt(3)*.004:
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
            base["samples"] += 1
            clearance = min(clearance, geometry["path_min_clearance_m"])
            if not geometry["passed"]:
                return {**base, **geometry, "at": pose}
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


    def _geometry_at(self, pose):
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
        nearby = self.points[self.tree.query_ball_point(xyz, self.radius+.02)]
        counts, scene_hits = collision_counts(nearby, xyz, site, self.geometry, self.opening,
                                              clearance_m=.004, return_points=True)
        own_points = self.target[self.target_tree.query_ball_point(xyz, self.radius+.02)] if self.target_tree is not None else self.target
        own, target_hits = collision_counts(own_points, xyz, site, self.geometry, self.opening,
                                            clearance_m=.004, return_points=True)
        if self.contact_allowed:
            own = {k: v for k, v in own.items() if k == "palm"}
        if any(counts.values()) or any(own.values()):
            result = {"passed": False, "reason": "measured_sweep_collision", "collision": True,
                "counts": counts, "target_counts": own, "path_min_clearance_m": 0.,
                "public_scene_collision_points": scene_hits, "public_target_collision_points": target_hits,
                "public_nearby_points": nearby[:256].tolist()}
        else:
            clearance = .2
            target_boxes = [b for b in self.geometry['boxes'] if not self.contact_allowed or b['name'] == 'palm']
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
                    result.update(passed=False, reason="measured_payload_collision", collision=True,
                        path_min_clearance_m=payload_clearance,
                        payload_point=world_payload[at].tolist(),
                        obstacle_point=self.points[neighbours[at]].tolist())
        self._pose_geometry_cache[key] = result
        return result
