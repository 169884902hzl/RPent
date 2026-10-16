"""Remove rendered robot surfaces using its static visual meshes and joints."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import _rotation, _vector, stl_vertices


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


def remove_visual_robot(points, pose_screen):
    """Account for rendered shells that extend outside collision meshes.

    This is a current-pose self filter, not future-arm collision screening.
    No general workspace carve or object simulator identity is used.
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
        ids = np.flatnonzero(((local >= lower-.002)&(local <= upper+.002)).all(axis=1)&~removed)
        count = 0
        for batch in np.array_split(ids, max(1, (len(ids)+255)//256)):
            inside = (local[batch]@equations[:, :3].T+equations[:, 3] <= .002).all(axis=1)
            removed[batch[inside]] = True
            count += int(inside.sum())
        counts[name] = count
    return cloud[~removed], {"source": "static_robot_visual_meshes_and_public_proprioception",
                             "removed_points": int(removed.sum()), "per_mesh": counts}
