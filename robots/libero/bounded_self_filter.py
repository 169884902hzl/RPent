"""Remove rendered robot surfaces using its static visual meshes and joints."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import _rotation, _vector, stl_vertices


def remove_current_gripper(points, eef_xyz, body_quat, geometry, opening, *, surface_margin_m=.0025):
    """Filter current mesh interiors, retaining nearby external obstacles.

    Unlike the historical 6 mm AABB carve, the narrow shell uses actual
    convex mesh membership. The 2.5 mm raster band covers the measured
    2.0--2.3 mm visual edge residual; space beyond it remains an obstacle.
    """
    cloud = np.asarray(points, float).reshape(-1, 3)
    site = Rotation.from_quat(body_quat).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    local = (cloud-np.asarray(eef_xyz))@site
    removed = np.zeros(len(cloud), bool)
    for box in geometry['boxes']:
        shift = np.asarray(box.get('slide_per_half_opening', [0., 0., 0.]))*opening/2
        positions = local-shift
        broad = ((positions >= np.asarray(box['lower'])-surface_margin_m)
                 & (positions <= np.asarray(box['upper'])+surface_margin_m)).all(axis=1)
        ids = np.flatnonzero(broad & ~removed)
        equations = box.get('convex_halfspaces')
        if equations is None:
            removed[ids] = True
            continue
        equations = np.asarray(equations)
        for batch in np.array_split(ids, max(1, (len(ids)+255)//256)):
            inside = (positions[batch]@equations[:, :3].T+equations[:, 3] <= surface_margin_m).all(axis=1)
            removed[batch[inside]] = True
    return cloud[~removed], int(removed.sum())


@lru_cache(maxsize=2)
def visual_hulls(xml_path: str):
    path = Path(xml_path)
    root = ET.parse(path).getroot()
    meshes = {m.get("name"): m for m in root.findall("asset/mesh")}
    body, node, result = root.find("worldbody/body"), 0, []
    while body is not None:
        for geom in body.findall("geom"):
            if geom.get("group") != "1" or geom.get("type") != "mesh":
                continue
            mesh = meshes[geom.get("mesh")]
            file = path.parent/mesh.get("file")
            if file.suffix.lower() == ".obj":
                vertices = np.array([line.split()[1:4] for line in file.read_text().splitlines()
                                     if line.startswith("v ")], float)
            else:
                vertices = stl_vertices(file)
            vertices = vertices*_vector(mesh, "scale", "1 1 1")
            vertices = vertices@_rotation(geom).T+_vector(geom, "pos", "0 0 0")
            if len(vertices) >= 4:
                hull = ConvexHull(vertices)
                result.append((node, file.name, vertices.min(axis=0), vertices.max(axis=0), hull.equations))
        if body.get("name") == "right_hand":
            break
        body, node = body.find("body"), node+1
    return result


def remove_visual_robot(points, pose_screen, *, surface_margin_m=.004):
    """Account for rendered shells that extend outside collision meshes.

    This is a current-pose self filter, not future-arm collision screening.
    No general workspace carve or object simulator identity is used. The
    4 mm band matches the route's measured-cloud clearance: at 256 px, link7
    edge pixels in motion job7512 lay 2.0--2.3 mm outside its static visual
    hull, beyond the old 2 mm filter. This band applies only to current robot
    surfaces; the scene collision clearance is unchanged.
    """
    cloud = np.asarray(points, float)
    base = (cloud-pose_screen.world_offset)@pose_screen.world_rotation
    transforms, transform, joint = [], np.eye(4), 0
    for fixed, axis in pose_screen.nodes:
        transform = transform@fixed
        if axis is not None:
            turn = np.eye(4)
            turn[:3, :3] = Rotation.from_rotvec(axis*pose_screen.joints[joint]).as_matrix()
            transform = transform@turn
            joint += 1
        transforms.append(transform.copy())
    removed, counts = np.zeros(len(cloud), bool), {}
    for node, name, lower, upper, equations in visual_hulls(pose_screen.reference["path"]):
        pose = transforms[node]
        local = (base-pose[:3, 3])@pose[:3, :3]
        ids = np.flatnonzero(((local >= lower-surface_margin_m)&(local <= upper+surface_margin_m)).all(axis=1)&~removed)
        count = 0
        for batch in np.array_split(ids, max(1, (len(ids)+255)//256)):
            inside = (local[batch]@equations[:, :3].T+equations[:, 3] <= surface_margin_m).all(axis=1)
            removed[batch[inside]] = True
            count += int(inside.sum())
        counts[name] = count
    return cloud[~removed], {"source": "static_robot_visual_meshes_and_public_proprioception",
                             "removed_points": int(removed.sum()), "per_mesh": counts,
                             "surface_margin_m": surface_margin_m}
