"""Remove rendered robot surfaces using its static visual meshes and joints."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from robots.libero.v5_geometric_grasp import _rotation, _vector, stl_vertices

ROBOT_FILTER_MARGIN_M = .012  # > 4 mm swept collision margin, USER 2026-10-20.


def remove_depth_edge_fliers(world):
    """Remove isolated depth samples adjacent to a depth discontinuity.

    A surface edge with two supporting neighbours is retained. No simulator
    segmentation or object identity is consulted.
    """
    points = np.asarray(world)
    if points.ndim == 2:
        return points.copy(), {'removed_depth_fliers':0,'reason':'unorganized_cloud_has_no_pixel_adjacency'}
    valid = np.isfinite(points).all(axis=-1) & (np.abs(points).sum(axis=-1) > 1e-6)
    support = np.zeros(valid.shape, np.uint8)
    discontinuity = np.zeros(valid.shape, bool)
    for axis in (0, 1):
        a, b = [slice(None), slice(None)], [slice(None), slice(None)]
        a[axis], b[axis] = slice(1, None), slice(None, -1)
        a, b = tuple(a), tuple(b)
        both = valid[a] & valid[b]
        close = np.linalg.norm(points[a]-points[b], axis=-1) <= .02
        support[a] += both & close
        support[b] += both & close
        discontinuity[a] |= both & ~close
        discontinuity[b] |= both & ~close
    outlier = valid & discontinuity & (support < 2)
    result = np.array(points, copy=True)
    result[outlier] = np.nan
    return result, {'removed_depth_fliers': int(outlier.sum()), 'neighbour_gap_m': .02,
                    'minimum_supported_neighbours': 2}


def public_robot_mask(world, robot, gripper_xml):
    """Locate robot pixels using only current proprioception and static meshes."""
    from scipy.spatial import cKDTree

    from robots.libero.v5_geometric_grasp import panda_geometry
    from robots.libero.v5_grasp_kinematics import PublicPoseScreen

    xml = Path(gripper_xml)
    geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
    hand = gripper_at_measured_fingers(geometry, robot['finger_positions_m'])
    points = np.asarray(world, float).reshape(-1, 3)
    valid = np.isfinite(points).all(axis=1) & (np.abs(points).sum(axis=1) > 1e-6)
    cloud, _ = remove_current_gripper(points[valid], robot['eef_xyz_m'], robot['eef_quat_xyzw'],
                                     hand, robot['gripper_opening_m'], surface_margin_m=ROBOT_FILTER_MARGIN_M)
    ik = PublicPoseScreen(xml.parent.parent/'robots/panda/robot.xml', robot['joint_positions_rad'],
        robot['eef_xyz_m'], robot['eef_quat_xyzw'], geometry['site_offset_in_gripper_m'])
    cloud, _ = ik.remove_measured_arm(cloud, tolerance_m=ROBOT_FILTER_MARGIN_M)
    cloud, _ = remove_visual_robot(cloud, ik, surface_margin_m=ROBOT_FILTER_MARGIN_M)
    removed = np.zeros(len(points), bool)
    removed[valid] = cKDTree(cloud).query(points[valid],
        distance_upper_bound=np.nextafter(1e-6, np.inf))[0] > 1e-6
    return removed.reshape(np.shape(world)[:2])


def gripper_at_measured_fingers(geometry, finger_qpos):
    """Place Panda finger shells from each public joint, without symmetry.

    During contact one finger can stop before the other. A summed aperture
    does not locate either shell; retain the actual slide of both joints.
    The returned geometry is fixed at this capture, for filtering and sweep.
    """
    positions = np.abs(np.asarray(finger_qpos, float))
    if positions.shape != (2,) or not np.isfinite(positions).all():
        raise ValueError('two measured Panda finger positions are required')
    result = dict(geometry)
    for group in ('boxes', 'visual_boxes'):
        if group not in geometry:
            continue
        result[group] = []
        for box in geometry[group]:
            name = box['name']
            finger = (0 if name.startswith('leftfinger') or name == 'finger1_visual' else
                      1 if name.startswith('rightfinger') or name == 'finger2_visual' else None)
            shift = np.asarray(box.get('slide_per_half_opening', [0., 0., 0.])) * (
                positions[finger] if finger is not None else 0.)
            measured = {**box, 'lower': (np.asarray(box['lower'])+shift).tolist(),
                        'upper': (np.asarray(box['upper'])+shift).tolist(),
                        'slide_per_half_opening': [0., 0., 0.]}
            if box.get('convex_halfspaces') is not None:
                equations = np.array(box['convex_halfspaces'], copy=True)
                equations[:, 3] -= equations[:, :3]@shift
                measured['convex_halfspaces'] = equations.tolist()
            result[group].append(measured)
    return result


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
    for box in geometry.get('visual_boxes', geometry['boxes']):
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
def gripper_visual_boxes(xml_path):
    """Static rendered gripper shells in the same grip-site frame as r9."""
    path = Path(xml_path)
    root = ET.parse(path).getroot()
    meshes = {mesh.get('name'): path.parent/mesh.get('file') for mesh in root.findall('asset/mesh')}
    hand = root.find(".//body[@name='right_gripper']")
    eef = hand.find("body[@name='eef']")
    offset = _vector(eef, 'pos', '0 0 0')+_vector(eef.find("site[@name='grip_site']"), 'pos', '0 0 0')
    result = []
    for body, sign in [(hand, 0), (hand.find("body[@name='leftfinger']"), 1),
                       (hand.find("body[@name='rightfinger']"), -1)]:
        rotation = _rotation(body) if sign else np.eye(3)
        position = _vector(body, 'pos', '0 0 0') if sign else np.zeros(3)
        slide = rotation@_vector(body.find('joint'), 'axis', '0 1 0')*sign if sign else np.zeros(3)
        for geom in body.findall('geom'):
            if geom.get('group') != '1' or geom.get('type') != 'mesh':
                continue
            vertices = stl_vertices(meshes[geom.get('mesh')])
            vertices = (vertices@_rotation(geom).T+_vector(geom, 'pos', '0 0 0'))@rotation.T+position-offset
            result.append({'name': geom.get('name'), 'lower': vertices.min(0), 'upper': vertices.max(0),
                'convex_halfspaces': ConvexHull(vertices).equations, 'slide_per_half_opening': slide})
    return result


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
        # Transform only points inside a conservative base-frame bound of
        # this same expanded local box. The original local-box and hull
        # tests below still decide membership, with unchanged tolerances.
        corners = np.array(np.meshgrid(*zip(lower-surface_margin_m,
            upper+surface_margin_m), indexing='ij')).reshape(3, -1).T
        corners = corners@pose[:3, :3].T+pose[:3, 3]
        rounding = 32*np.finfo(float).eps*(1+np.max(np.abs(corners)))
        broad = ((base >= corners.min(axis=0)-rounding)
                 & (base <= corners.max(axis=0)+rounding)).all(axis=1)&~removed
        ids = np.flatnonzero(broad)
        local = (base[ids]-pose[:3, 3])@pose[:3, :3]
        inside_box = ((local >= lower-surface_margin_m)&(local <= upper+surface_margin_m)).all(axis=1)
        ids, local = ids[inside_box], local[inside_box]
        count = 0
        for batch in np.array_split(np.arange(len(ids)), max(1, (len(ids)+255)//256)):
            inside = (local[batch]@equations[:, :3].T+equations[:, 3] <= surface_margin_m).all(axis=1)
            removed[ids[batch[inside]]] = True
            count += int(inside.sum())
        counts[name] = count
    return cloud[~removed], {"source": "static_robot_visual_meshes_and_public_proprioception",
                             "removed_points": int(removed.sum()), "per_mesh": counts,
                             "surface_margin_m": surface_margin_m}
